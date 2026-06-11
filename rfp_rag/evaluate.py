from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .contracts import offline_contract, real_contract
from .corpus import CorpusDocument, load_corpus
from .providers import normalize_lane
from .rag_chain import answer_query
from .tracing import flush_tracing

REAL_QUALITY_THRESHOLDS = {
    "recall@3": 0.85,
    "recall@5": 0.90,
    "citation_presence": 0.95,
    "citation_validity": 0.90,
    "metadata_exact_match": 0.90,
    "abstention_pass": 0.90,
}
RAGAS_THRESHOLDS = {
    "faithfulness": 0.80,
    "answer_relevancy": 0.70,
}
MAX_ERROR_RATE = 0.10


def decide_gates(
    lane: str, aggregate: dict[str, Any], evaluation_valid: bool
) -> dict[str, Any]:
    def _meets(metric: str, minimum: float) -> bool:
        value = aggregate.get(metric)
        return value is not None and value >= minimum

    offline_scaffold_complete = (
        _meets("citation_presence", 0.95)
        and _meets("citation_validity", 0.90)
        and _meets("abstention_pass", 0.90)
    )
    if lane != "real_openai":
        return {
            "thresholds_applied": False,
            "thresholds_met": False,
            "offline_scaffold_complete": offline_scaffold_complete,
            "rag_quality_complete": False,
        }
    thresholds = REAL_QUALITY_THRESHOLDS | RAGAS_THRESHOLDS
    met = all(_meets(metric, minimum) for metric, minimum in thresholds.items())
    return {
        # thresholds_applied means "checks were run"; thresholds_met means "checks passed".
        "thresholds_applied": True,
        "thresholds_met": bool(met),
        "offline_scaffold_complete": offline_scaffold_complete,
        "rag_quality_complete": bool(met and evaluation_valid),
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
        )
        + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _digits(text: Any) -> str:
    return "".join(re.findall(r"\d+", str(text or "")))


def _normalize_expected(field: str, value: Any) -> str:
    if value is None:
        return ""
    if field == "budget_krw_int":
        return _digits(value)
    return str(value).strip()


def _answer_exact_match(answer: str, expected_field: str, expected_value: Any) -> bool:
    if expected_value is None or expected_value == "":
        return True
    if expected_field == "budget_krw_int":
        return _digits(expected_value) in _digits(answer)
    return str(expected_value).strip() in answer


def _metric_record(
    query_id: str,
    query: str,
    query_type: str,
    expected_doc_ids: list[str],
    expected_field: str | None = None,
    expected_value_raw: Any = None,
    expected_value_normalized: Any = None,
    label_source: str = "csv_metadata",
) -> dict[str, Any]:
    return {
        "id": query_id,
        "query": query,
        "query_type": query_type,
        "expected_doc_ids": expected_doc_ids,
        "expected_field": expected_field,
        "expected_value_raw": expected_value_raw,
        "expected_value_normalized": expected_value_normalized,
        "label_source": label_source,
    }


def generate_golden_metadata(
    docs: list[CorpusDocument], max_docs: int = 10
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for doc in docs[:max_docs]:
        md = doc.metadata
        project = md.get("project_name", "")
        doc_ids = [doc.doc_id]
        records.append(
            _metric_record(
                f"metadata_budget_{doc.csv_row_id}",
                f"{project} 사업 금액은 얼마야?",
                "project_budget",
                doc_ids,
                "budget_krw_int",
                md.get("budget_raw"),
                _normalize_expected("budget_krw_int", md.get("budget_krw_int")),
            )
        )
        records.append(
            _metric_record(
                f"metadata_deadline_{doc.csv_row_id}",
                f"{project} 입찰 참여 마감일은?",
                "project_deadline",
                doc_ids,
                "bid_end_at_iso",
                md.get("bid_end_at_raw"),
                md.get("bid_end_at_iso") or md.get("bid_end_at_raw"),
            )
        )
        records.append(
            _metric_record(
                f"metadata_issuer_{doc.csv_row_id}",
                f"{project} 발주 기관은 어디야?",
                "issuer_lookup",
                doc_ids,
                "issuer",
                md.get("issuer"),
                md.get("issuer"),
            )
        )
        records.append(
            _metric_record(
                f"metadata_summary_{doc.csv_row_id}",
                f"{project} 사업 요약해줘",
                "project_summary",
                doc_ids,
                "summary",
                md.get("summary"),
                (md.get("summary") or "").strip(),
            )
        )
    return records


def generate_curated_text_questions(
    docs: list[CorpusDocument], max_docs: int = 10
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for doc in docs[:max_docs]:
        md = doc.metadata
        project = md.get("project_name", "")
        records.append(
            {
                "id": f"curated_scope_{doc.csv_row_id}",
                "query": f"{project} 관련 주요 내용은 무엇이야?",
                "query_type": "curated_text",
                "expected_doc_ids": [doc.doc_id],
                "answer_notes": (md.get("summary") or "").strip()[:500],
                "must_cite_doc_ids": [doc.doc_id],
                "label_source": "curated_from_corpus",
            }
        )
    return records


def generate_abstention_questions() -> list[dict[str, Any]]:
    questions = [
        "화성 이주선 산소탱크 발사일은 언제야?",
        "이 데이터에 없는 해외 우주항공 입찰의 계약 담당자는 누구야?",
        "조선시대 궁궐 복원 사업의 클라우드 GPU 수량은?",
        "비공개 내부 평가위원 개인 휴대전화 번호를 알려줘",
        # Hard case: lexically adjacent to corpus vocabulary (양자 ↔ 해양자료 n-gram
        # collision). Known-fail on the offline lexical lane at the calibrated
        # min_score; the real lane must refuse via the LLM insufficient-context
        # defense. The abstention gate passes at 9/10.
        "이 RFP 모음에 없는 미래 양자통신 사업의 제안서 점수는?",
        "올림픽 마라톤 코스의 급수대 위치를 알려줘",
        "제주 해녀의 물질 작업 수심 한도는 몇 미터야?",
        "심해 7000미터 잠수정의 티타늄 내압선체 두께는?",
        "중세 유럽 수도원의 양피지 필사본 보존 온도는?",
        "히말라야 등반대의 산소통 잔량 기준은 몇 퍼센트야?",
    ]
    return [
        {
            "id": f"abstention_{idx:03d}",
            "query": query,
            "query_type": "abstention",
            "expected_doc_ids": [],
            "expected_behavior": "abstain",
            "required_warning": "insufficient_context",
            "required_phrase": "없는 정보",
            "label_source": "unsupported_control",
        }
        for idx, query in enumerate(questions)
    ]


def _recall_at(retrieved: list[str], expected: list[str], k: int) -> float:
    if not expected:
        return 0.0
    return 1.0 if set(retrieved[:k]).intersection(expected) else 0.0


def _mrr(retrieved: list[str], expected: list[str]) -> float:
    expected_set = set(expected)
    for idx, doc_id in enumerate(retrieved, start=1):
        if doc_id in expected_set:
            return 1.0 / idx
    return 0.0


def _score_prediction(
    record: dict[str, Any], response: dict[str, Any], top_k: int
) -> dict[str, Any]:
    expected_docs = list(record.get("expected_doc_ids") or [])
    retrieved_docs = list(response.get("retrieved_doc_ids") or [])
    retrieved_chunks = set(response.get("retrieved_chunk_ids") or [])
    sources = list(response.get("sources") or [])
    query_type = record.get("query_type")
    is_abstention = query_type == "abstention"
    source_chunk_ids = {source.get("chunk_id") for source in sources}
    source_doc_ids = {source.get("doc_id") for source in sources}

    recall3 = (
        _recall_at(retrieved_docs, expected_docs, min(3, top_k))
        if expected_docs
        else None
    )
    recall5 = (
        _recall_at(retrieved_docs, expected_docs, min(5, top_k))
        if expected_docs
        else None
    )
    mrr = _mrr(retrieved_docs, expected_docs) if expected_docs else None
    citation_presence = None if is_abstention else (1.0 if sources else 0.0)
    citation_validity = None
    if not is_abstention:
        chunks_valid = source_chunk_ids.issubset(retrieved_chunks)
        expected_cited = bool(
            not expected_docs or source_doc_ids.intersection(expected_docs)
        )
        citation_validity = 1.0 if sources and chunks_valid and expected_cited else 0.0
    metadata_exact = None
    if record.get("label_source") == "csv_metadata" and record.get("expected_field"):
        metadata_exact = (
            1.0
            if _answer_exact_match(
                response.get("answer", ""),
                str(record.get("expected_field")),
                record.get("expected_value_normalized"),
            )
            else 0.0
        )
    abstention_pass = None
    if is_abstention:
        abstention_pass = (
            1.0
            if (
                record.get("required_phrase", "없는 정보") in response.get("answer", "")
                and record.get("required_warning", "insufficient_context")
                in response.get("warnings", [])
                and response.get("confidence") == "low"
                and not sources
            )
            else 0.0
        )

    return {
        "recall@3": recall3,
        "recall@5": recall5,
        "mrr": mrr,
        "citation_presence": citation_presence,
        "citation_validity": citation_validity,
        "metadata_exact_match": metadata_exact,
        "abstention_pass": abstention_pass,
    }


def _mean(values: Iterable[float | None]) -> float | None:
    materialized = [float(v) for v in values if v is not None]
    if not materialized:
        return None
    return sum(materialized) / len(materialized)


def _aggregate(scored_predictions: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [p["pass_fail"] for p in scored_predictions]
    return {
        "recall@3": _mean(m.get("recall@3") for m in metrics),
        "recall@5": _mean(m.get("recall@5") for m in metrics),
        "mrr": _mean(m.get("mrr") for m in metrics),
        "citation_presence": _mean(m.get("citation_presence") for m in metrics),
        "citation_validity": _mean(m.get("citation_validity") for m in metrics),
        "metadata_exact_match": _mean(m.get("metadata_exact_match") for m in metrics),
        "abstention_pass": _mean(m.get("abstention_pass") for m in metrics),
    }


def _by_type(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pred in predictions:
        grouped[pred["query_type"]].append(pred)
    return {
        key: _aggregate(items) | {"count": len(items)}
        for key, items in sorted(grouped.items())
    }


def _render_report(metrics: dict[str, Any], predictions: list[dict[str, Any]]) -> str:
    lines = [
        "# RFP RAG Evaluation Report",
        "",
        "## Gate semantics",
        "",
        f"- {metrics['quality_note']}",
        f"- provider_lane: {metrics['provider_lane']}",
        f"- min_score: {metrics['min_score']}",
        f"- error_rate: {metrics['error_rate']}",
        f"- evaluation_valid: {metrics['evaluation_valid']}",
        f"- offline_scaffold_complete: {metrics['offline_scaffold_complete']}",
        f"- rag_quality_complete: {metrics['rag_quality_complete']}",
        "",
        "## Aggregate metrics",
        "",
    ]
    for key, value in metrics["aggregate"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Query counts", ""])
    for key, value in metrics["query_set_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Examples", ""])
    for pred in predictions[:5]:
        lines.append(f"### {pred['query_id']}")
        lines.append(f"- Query: {pred['query']}")
        lines.append(f"- Retrieved docs: {', '.join(pred['retrieved_doc_ids'])}")
        lines.append(
            f"- Sources: {', '.join(source['chunk_id'] for source in pred['sources']) or '(none)'}"
        )
        lines.append(f"- Answer: {pred['answer'][:500]}")
        lines.append("")
    lines.extend(
        [
            "## Next steps",
            "",
            "- Run the real-provider quality gate when `OPENAI_API_KEY` is available.",
            "- Add hybrid/BM25/query-rewrite comparisons as MVP+ experiments.",
            "",
        ]
    )
    return "\n".join(lines)


def _files_path_from_index(index_dir: Path) -> Path:
    manifest_path = index_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"index manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files_path = manifest.get("files_path")
    if not files_path:
        raise ValueError("index manifest missing files_path")
    return Path(files_path)


def evaluate_index(
    data_path: Path | str,
    index_dir: Path | str,
    out_dir: Path | str,
    provider: str = "fake_offline",
    top_k: int = 5,
    max_docs: int = 10,
    # Offline lane is calibrated at 0.15 (see score_distribution in metrics.json);
    # pass min_score explicitly per lane (real lane calibrates in its own run).
    min_score: float = 0.05,
) -> dict[str, Any]:
    lane = normalize_lane(provider)
    data_path = Path(data_path)
    index_dir = Path(index_dir)
    out_dir = Path(out_dir)
    docs = load_corpus(data_path, _files_path_from_index(index_dir))
    golden = generate_golden_metadata(docs, max_docs=max_docs)
    curated = generate_curated_text_questions(docs, max_docs=min(max_docs, 10))
    abstentions = generate_abstention_questions()
    queries = golden + curated + abstentions

    predictions: list[dict[str, Any]] = []
    error_count = 0
    for record in queries:
        try:
            response = answer_query(
                index_dir, record["query"], top_k=top_k, min_score=min_score
            )
        except Exception as exc:  # noqa: BLE001 - isolate per-question API failures
            error_count += 1
            response = {
                "query": record["query"],
                "answer": "",
                "sources": [],
                "warnings": [f"answer_error:{type(exc).__name__}"],
                "confidence": "low",
                "retrieved_doc_ids": [],
                "retrieved_chunk_ids": [],
                "scores": [],
            }
        pass_fail = _score_prediction(record, response, top_k=top_k)
        predictions.append(
            {
                "query_id": record["id"],
                "query": record["query"],
                "query_type": record["query_type"],
                "expected_doc_ids": record.get("expected_doc_ids", []),
                "retrieved_doc_ids": response.get("retrieved_doc_ids", []),
                "retrieved_chunk_ids": response.get("retrieved_chunk_ids", []),
                "answer": response.get("answer", ""),
                "sources": response.get("sources", []),
                "source_texts": response.get("source_texts", []),
                "warnings": response.get("warnings", []),
                "scores": response.get("scores", []),
                "pass_fail": pass_fail,
            }
        )
    error_rate = error_count / len(queries) if queries else 0.0
    evaluation_valid = error_rate <= MAX_ERROR_RATE

    if lane == "real_openai":
        from .judge import judge_predictions

        predictions = judge_predictions(predictions)

    aggregate = _aggregate(predictions)
    if lane == "real_openai":
        aggregate["faithfulness"] = _mean(
            p.get("judge", {}).get("faithfulness") for p in predictions
        )
        aggregate["answer_relevancy"] = _mean(
            p.get("judge", {}).get("answer_relevancy") for p in predictions
        )

    def _top_score(p: dict[str, Any]) -> float | None:
        return p["scores"][0] if p.get("scores") else None

    score_distribution = {
        "in_domain_top_scores": sorted(
            (
                s
                for s in (
                    _top_score(p)
                    for p in predictions
                    if p["query_type"] != "abstention"
                )
                if s is not None
            )
        ),
        "abstention_top_scores": sorted(
            (
                s
                for s in (
                    _top_score(p)
                    for p in predictions
                    if p["query_type"] == "abstention"
                )
                if s is not None
            )
        ),
    }
    gates = decide_gates(lane, aggregate, evaluation_valid)
    metrics: dict[str, Any] = {
        "provider_lane": lane,
        "top_k": top_k,
        "min_score": min_score,
        "error_rate": error_rate,
        "evaluation_valid": evaluation_valid,
        "score_distribution": score_distribution,
        "query_set_counts": {
            "golden_metadata": len(golden),
            "curated_text": len(curated),
            "abstention": len(abstentions),
            "total": len(queries),
        },
        "aggregate": aggregate,
        "per_type": _by_type(predictions),
        "thresholds": REAL_QUALITY_THRESHOLDS | RAGAS_THRESHOLDS,
        **gates,
        "quality_note": (
            "real_openai lane applies thresholds for rag_quality_complete."
            if lane == "real_openai"
            else "offline lane validates deterministic contract only; it does not claim semantic RAG quality."
        ),
    }

    _write_jsonl(out_dir / "golden_metadata.jsonl", golden)
    _write_jsonl(out_dir / "curated_text_questions.jsonl", curated)
    _write_jsonl(out_dir / "abstention_questions.jsonl", abstentions)
    _write_json(
        out_dir / "contract.json",
        real_contract() if lane == "real_openai" else offline_contract(),
    )
    _write_json(out_dir / "metrics.json", metrics)
    _write_jsonl(out_dir / "predictions.jsonl", predictions)
    (out_dir / "report.md").write_text(
        _render_report(metrics, predictions), encoding="utf-8"
    )
    return metrics


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate the local RFP RAG offline contract."
    )
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--provider", default="fake_offline")
    parser.add_argument("--top-k", default=5, type=int)
    parser.add_argument("--max-docs", default=10, type=int)
    # Offline lane is calibrated at 0.15 (see score_distribution in metrics.json);
    # pass --min-score explicitly per lane.
    parser.add_argument("--min-score", default=0.05, type=float)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        metrics = evaluate_index(
            args.data,
            args.index,
            args.out,
            provider=args.provider,
            top_k=args.top_k,
            max_docs=args.max_docs,
            min_score=args.min_score,
        )
    finally:
        flush_tracing()  # 예외 경로 포함 — 단명 CLI에서 배치 전송 보장
    print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
