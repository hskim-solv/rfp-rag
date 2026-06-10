from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

from ..contracts import agent_contract
from ..corpus import CorpusDocument
from ..evaluate import (
    MAX_ERROR_RATE,
    _answer_exact_match,
    generate_abstention_questions,
    generate_golden_metadata,
)
from ..rag_chain import DEFAULT_MIN_SCORE
from ..vector_index import search
from .graph import build_agent_graph, initial_state, run_config
from .nodes import AgentRuntime
from .run_agent import build_runtime

AGENT_THRESHOLDS: dict[str, float] = {
    "routing_accuracy": 0.90,
    "tool_accuracy": 0.90,
    "rewrite_recovery": 0.60,
    "loop_termination": 1.0,
    "abstention_accuracy": 0.90,
    "citation_presence": 0.95,
    "citation_validity": 0.90,
    "metadata_exact_match": 0.90,
}

NOISY_PREFIX = (
    "안녕하세요 혹시 다른 건 말고 그게 궁금한데요 그러면 근데 그런데 아니면 "
    "혹은 그리고 좀 대해서 관련해서 궁금한데 있을까요 "
)
MAX_NOISE_LEVEL = 4
_SINGLE_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


def decide_agent_gate(metrics: dict[str, Any], evaluation_valid: bool) -> dict[str, Any]:
    failed = [
        name
        for name, minimum in AGENT_THRESHOLDS.items()
        if metrics.get(name) is None or metrics[name] < minimum
    ]
    return {
        "thresholds_applied": True,
        "thresholds": dict(AGENT_THRESHOLDS),
        "failed": failed,
        "evaluation_valid": evaluation_valid,
        "agent_lane_complete": evaluation_valid and not failed,
    }


# --- scenario generation ------------------------------------------------------


def _routing_scenarios(docs: list[CorpusDocument]) -> list[dict[str, Any]]:
    """rag 10건(golden 질문) + metadata 10건(규칙 패턴). 기대 route만 채점."""
    rag = generate_golden_metadata(docs, max_docs=3)[:10]
    cases = [
        {
            "id": f"routing_rag_{i:03d}",
            "type": "routing",
            "question": r["query"],
            "expected_route": "rag_query",
        }
        for i, r in enumerate(rag)
    ]
    issuer = _single_token_issuer(docs)
    metadata_questions = [
        "사업 금액이 가장 큰 공고 3건은 뭐야?",
        "사업 금액이 가장 큰 공고 5건 알려줘",
        "입찰 마감이 가장 빠른 공고 5건 알려줘",
        "입찰 마감이 가장 빠른 공고 3건은?",
        "사업 금액이 10억 이상인 공고는 몇 건이야?",
        "사업 금액이 5억 이상인 공고는 몇 건이야?",
        "전체 공고는 몇 건이야?",
        f"{issuer}이 발주한 공고는 몇 건이야?",
        "사업 금액이 10억 이상인 공고들의 금액 합계는 얼마야?",
        "사업 금액이 가장 높은 공고 1건은?",
    ]
    cases += [
        {
            "id": f"routing_meta_{i:03d}",
            "type": "routing",
            "question": q,
            "expected_route": "metadata_query",
        }
        for i, q in enumerate(metadata_questions)
    ]
    return cases


def _regression_scenarios(docs: list[CorpusDocument]) -> list[dict[str, Any]]:
    """기존 golden 생성/채점 로직 재사용 (5 docs × 4 fields = 20건)."""
    golden = generate_golden_metadata(docs, max_docs=5)[:20]
    return [
        {
            "id": f"regression_{i:03d}",
            "type": "regression",
            "question": g["query"],
            "expected_doc_id": g["expected_doc_ids"][0],
            "expected_field": g["expected_field"],
            "expected_value": g["expected_value_normalized"],
        }
        for i, g in enumerate(golden)
    ]


def _rewrite_scenarios(
    docs: list[CorpusDocument], runtime: AgentRuntime, min_score: float
) -> list[dict[str, Any]]:
    """노이즈 질의 스코어가 min_score 미달인 변형만 채택 — rewrite 트리거를 결정론으로 보장.

    lexical 임베딩은 희석에 둔감하므로 프리픽스 반복 횟수(noise_level)를 1→MAX로 올리며
    처음으로 미달하는 변형을 쓴다.
    """
    golden = generate_golden_metadata(docs, max_docs=10)
    out: list[dict[str, Any]] = []
    for g in golden:
        chosen = None
        for level in range(1, MAX_NOISE_LEVEL + 1):
            noisy = NOISY_PREFIX * level + g["query"]
            results = search(runtime.store, noisy, top_k=1)
            if results and results[0].score < min_score:
                chosen = (noisy, level)
                break
        if chosen is None:
            continue
        noisy, level = chosen
        out.append(
            {
                "id": f"rewrite_{len(out):03d}",
                "type": "rewrite",
                "question": noisy,
                "noise_level": level,
                "expected_doc_id": g["expected_doc_ids"][0],
                "expected_field": g["expected_field"],
                "expected_value": g["expected_value_normalized"],
            }
        )
        if len(out) == 5:
            break
    return out


def _abstention_scenarios() -> list[dict[str, Any]]:
    return [
        {"id": f"abstention_{i:03d}", "type": "abstention", "question": a["query"]}
        for i, a in enumerate(generate_abstention_questions())
    ]


def _single_token_issuer(docs: list[CorpusDocument]) -> str:
    """RuleRouter의 발주기관 정규식이 안전하게 잡는 단일 토큰 발주기관."""
    for d in docs:
        issuer = d.metadata.get("issuer") or ""
        if _SINGLE_TOKEN_RE.fullmatch(issuer):
            return issuer
    return "한국전력공사"


def _tool_scenarios(docs: list[CorpusDocument]) -> list[dict[str, Any]]:
    """기대값은 docs에서 독립 계산(인라인 sorted/sum) — 도구 구현과 분리된 채점 기준."""
    budgets = [(d.doc_id, d.metadata.get("budget_krw_int")) for d in docs]
    with_budget = [(i, b) for i, b in budgets if b is not None]
    top_budget = [i for i, _ in sorted(with_budget, key=lambda x: -x[1])]
    deadlines = [(d.doc_id, d.metadata.get("bid_end_at_iso")) for d in docs]
    with_deadline = sorted([(i, t) for i, t in deadlines if t], key=lambda x: x[1])
    gte_10e8 = [i for i, b in with_budget if b >= 1_000_000_000]
    sum_10e8 = sum(b for _, b in with_budget if b >= 1_000_000_000)
    issuer = _single_token_issuer(docs)
    issuer_count = sum(1 for d in docs if issuer in (d.metadata.get("issuer") or ""))
    cases = [
        {"question": "사업 금액이 가장 큰 공고 3건은 뭐야?", "expect": {"doc_ids": top_budget[:3]}},
        {"question": "사업 금액이 가장 큰 공고 5건 알려줘", "expect": {"doc_ids": top_budget[:5]}},
        {"question": "사업 금액이 가장 높은 공고 1건은?", "expect": {"doc_ids": top_budget[:1]}},
        {"question": "입찰 마감이 가장 빠른 공고 5건 알려줘", "expect": {"doc_ids": [i for i, _ in with_deadline[:5]]}},
        {"question": "입찰 마감이 가장 빠른 공고 3건은?", "expect": {"doc_ids": [i for i, _ in with_deadline[:3]]}},
        {"question": "사업 금액이 10억 이상인 공고는 몇 건이야?", "expect": {"count": len(gte_10e8)}},
        {"question": "전체 공고는 몇 건이야?", "expect": {"count": len(docs)}},
        {"question": f"{issuer}이 발주한 공고는 몇 건이야?", "expect": {"count": issuer_count}},
        {"question": "사업 금액이 10억 이상인 공고들의 금액 합계는 얼마야?", "expect": {"sum": sum_10e8}},
        {
            "question": "사업 금액이 5억 이상인 공고는 몇 건이야?",
            "expect": {"count": sum(1 for _, b in with_budget if b >= 500_000_000)},
        },
    ]
    return [
        {"id": f"tool_{i:03d}", "type": "tool", "question": c["question"], "expect": c["expect"]}
        for i, c in enumerate(cases)
    ]


# --- scoring -------------------------------------------------------------------


def _score_case(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    answer = result.get("answer") or {}
    answer_text = answer.get("answer") or ""
    scored: dict[str, Any] = {
        "id": case["id"],
        "type": case["type"],
        "question": case["question"],
        "route": result.get("route"),
        "outcome": result.get("outcome"),
        "rewrite_count": result.get("rewrite_count", 0),
        "loop_terminated": (result.get("rewrite_count", 0) or 0) <= 2,
    }
    kind = case["type"]
    if kind == "routing":
        scored["routing_correct"] = result.get("route") == case["expected_route"]
    elif kind in ("regression", "rewrite"):
        answered = result.get("outcome") == "answered"
        retrieved = answer.get("retrieved_doc_ids") or []
        sources = answer.get("sources") or []
        retrieved_chunks = set(answer.get("retrieved_chunk_ids") or [])
        cited = {s.get("chunk_id") for s in sources}
        scored["exact_match"] = answered and _answer_exact_match(
            answer_text, case["expected_field"], case["expected_value"]
        )
        scored["citation_present"] = bool(sources)
        scored["citation_valid"] = bool(cited) and cited <= retrieved_chunks
        scored["doc_hit"] = case["expected_doc_id"] in retrieved
        if kind == "rewrite":
            scored["recovered"] = scored["exact_match"]
    elif kind == "abstention":
        scored["abstained"] = result.get("outcome") == "abstained"
    elif kind == "tool":
        tr = result.get("tool_result") or {}
        expect = case["expect"]
        ok = result.get("route") == "metadata_query"
        for key, value in expect.items():
            ok = ok and tr.get(key) == value
        scored["tool_correct"] = ok
    return scored


def _mean(flags: list[bool]) -> float | None:
    return None if not flags else sum(1.0 for f in flags if f) / len(flags)


def _aggregate(scored: list[dict[str, Any]]) -> dict[str, Any]:
    def by(t: str) -> list[dict[str, Any]]:
        return [s for s in scored if s["type"] == t]

    reg = by("regression")
    return {
        "routing_accuracy": _mean([s["routing_correct"] for s in by("routing")]),
        "tool_accuracy": _mean([s["tool_correct"] for s in by("tool")]),
        "rewrite_recovery": _mean([s["recovered"] for s in by("rewrite")]),
        "loop_termination": _mean([s["loop_terminated"] for s in scored]),
        "abstention_accuracy": _mean([s["abstained"] for s in by("abstention")]),
        "citation_presence": _mean([s["citation_present"] for s in reg]),
        "citation_validity": _mean([s["citation_valid"] for s in reg]),
        "metadata_exact_match": _mean([s["exact_match"] for s in reg]),
        "counts": {t: len(by(t)) for t in ("routing", "regression", "rewrite", "abstention", "tool")},
    }


def _render_report(metrics: dict[str, Any], gate: dict[str, Any]) -> str:
    lines = ["# Agent Lane Evaluation", ""]
    for name, minimum in AGENT_THRESHOLDS.items():
        value = metrics.get(name)
        mark = "PASS" if (value is not None and value >= minimum) else "FAIL"
        shown = "null" if value is None else f"{value:.4f}"
        lines.append(f"- {name}: {shown} (>= {minimum}) {mark}")
    lines += [
        "",
        f"- counts: {json.dumps(metrics['counts'], ensure_ascii=False)}",
        f"- evaluation_valid: {gate['evaluation_valid']}",
        f"- **agent_lane_complete: {gate['agent_lane_complete']}**",
        "",
    ]
    return "\n".join(lines)


def evaluate_agent(
    data: Path,
    files: Path,
    index_dir: Path,
    out_dir: Path,
    provider: str | None,
    top_k: int,
    min_score: float,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    runtime = build_runtime(
        index_dir, data, files, provider, top_k, min_score,
        artifacts=out_dir / "agent_artifacts", thread_id="eval",
    )
    docs = runtime.docs
    scenarios = (
        _routing_scenarios(docs)
        + _regression_scenarios(docs)
        + _rewrite_scenarios(docs, runtime, min_score)
        + _abstention_scenarios()
        + _tool_scenarios(docs)
    )
    graph = build_agent_graph(runtime)
    scored: list[dict[str, Any]] = []
    errors = 0
    for i, case in enumerate(scenarios):
        try:
            result = graph.invoke(initial_state(case["question"]), run_config(f"eval-{i}"))
        except Exception as exc:  # 개별 실패는 기록하고 진행 (기존 evaluate 정책)
            errors += 1
            scored.append(
                {"id": case["id"], "type": case["type"], "error": str(exc), "loop_terminated": True}
            )
            continue
        scored.append(_score_case(case, result))
    evaluation_valid = (errors / max(len(scenarios), 1)) <= MAX_ERROR_RATE
    metrics = _aggregate([s for s in scored if "error" not in s])
    gate = decide_agent_gate(metrics, evaluation_valid=evaluation_valid)
    lane = runtime_lane(index_dir, provider)
    metrics_payload = {
        "lane": lane,
        "top_k": top_k,
        "min_score": min_score,
        "errors": errors,
        **metrics,
        "gate": gate,
        "agent_lane_complete": gate["agent_lane_complete"],
    }
    (out_dir / "scenarios.jsonl").write_text(
        "\n".join(json.dumps(s, ensure_ascii=False, sort_keys=True) for s in scenarios) + "\n",
        encoding="utf-8",
    )
    (out_dir / "predictions.jsonl").write_text(
        "\n".join(json.dumps(s, ensure_ascii=False, sort_keys=True) for s in scored) + "\n",
        encoding="utf-8",
    )
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "report.md").write_text(_render_report(metrics, gate), encoding="utf-8")
    (out_dir / "contract.json").write_text(
        json.dumps(agent_contract(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metrics_payload


def runtime_lane(index_dir: Path, provider: str | None) -> str:
    from ..providers import normalize_lane
    from ..rag_chain import _load_manifest

    if provider:
        return normalize_lane(provider)
    return normalize_lane(_load_manifest(index_dir).get("embedding_provider", "offline"))


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rfp_rag.agent.evaluate_agent")
    p.add_argument("--data", required=True, type=Path)
    p.add_argument("--files", required=True, type=Path)
    p.add_argument("--index", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--provider", default=None)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(list(argv) if argv is not None else None)
    payload = evaluate_agent(
        args.data, args.files, args.index, args.out, args.provider, args.top_k, args.min_score
    )
    print(
        json.dumps(
            {"agent_lane_complete": payload["agent_lane_complete"], "out": str(args.out)},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
