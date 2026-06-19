from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from rfp_rag.agent.brains import RuleQueryRewriter, RuleRouter
from rfp_rag.agent.graph import (
    build_agent_graph,
    close_checkpointer,
    initial_state,
    run_config,
    sqlite_checkpointer,
)
from rfp_rag.agent.nodes import AgentRuntime
from rfp_rag.agent.tools import AuditLogger, sanitize_audit_args
from rfp_rag.chunking import Chunk
from rfp_rag.corpus import CorpusDocument
from rfp_rag.ops_tool_server import ToolGuardrailError, ToolRegistry
from rfp_rag.providers import LexicalHashEmbeddings, TemplateAnswerGenerator
from rfp_rag.vector_index import build_vector_store, search


PROJECT = "한영대학교 트랙운영 학사정보시스템 고도화"
NOISY_PREFIX = (
    "안녕하세요 혹시 다른 건 말고 그게 궁금한데요 그러면 근데 그런데 아니면 "
    "혹은 그리고 좀 대해서 관련해서 궁금한데 있을까요 "
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
        + "\n",
        encoding="utf-8",
    )


def _runtime(
    root: Path, *, min_score: float = 0.05, thread_id: str = "agent-stress"
) -> AgentRuntime:
    chunks = [
        Chunk(
            chunk_id="doc:000:chunk:0",
            doc_id="doc:000",
            csv_row_id="000",
            text=f"{PROJECT} 사업 제안요청서 본문",
            metadata={
                "project_name": PROJECT,
                "issuer": "한영대학",
                "summary": "학사정보시스템 고도화 사업",
                "budget_krw_int": 130_000_000,
                "bid_end_at_iso": "2024-10-15T17:00:00",
                "csv_filename_raw": "han.hwp",
            },
        )
    ]
    store = build_vector_store(
        chunks, LexicalHashEmbeddings(dim=512), qdrant_path=None, lane="offline"
    )
    docs = [
        CorpusDocument(
            csv_row_id="000",
            doc_id="doc:000",
            text="본문",
            metadata={
                "project_name": PROJECT,
                "issuer": "한영대학",
                "budget_krw_int": 130_000_000,
                "bid_end_at_iso": "2024-10-15T17:00:00",
            },
        )
    ]
    return AgentRuntime(
        store=store,
        generator=TemplateAnswerGenerator(),
        router=RuleRouter(),
        rewriter=RuleQueryRewriter(),
        docs=docs,
        audit=AuditLogger(root / "artifacts/eval_agent_stress/audit.jsonl"),
        reports_dir=root / "artifacts/eval_agent_stress/reports",
        top_k=3,
        min_score=min_score,
        thread_id=thread_id,
    )


def _scenario_hash(scenarios: list[dict[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(scenarios, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _tool_budget_pass() -> bool:
    registry = ToolRegistry(allowed_tools=set(), max_tool_calls=0)
    try:
        registry.call_tool("eval.metrics", {})
    except ToolGuardrailError as exc:
        return exc.code in {"tool_not_allowed", "tool_budget_exceeded"}
    return False


def _state_redaction_pass() -> bool:
    sanitized = sanitize_audit_args(
        {"query": "OPENAI_API_KEY=sk-test-secret 010-1234-5678 사업 요약"}
    )
    serialized = json.dumps(sanitized, ensure_ascii=False)
    return (
        sanitized.get("query_preview") == "[REDACTED]"
        and "sk-test-secret" not in serialized
        and "010-1234-5678" not in serialized
    )


def _checkpoint_close_path_pass(root: Path) -> bool:
    checkpointer = sqlite_checkpointer(
        root / "artifacts/eval_agent_stress/checkpoints.sqlite"
    )
    return close_checkpointer(checkpointer)


def evaluate_agent_stress(
    *, root: Path = Path("."), out: Path | None = None
) -> dict[str, Any]:
    root = root.resolve()
    out = out or root / "artifacts/eval_agent_stress/metrics.json"
    replay_path = root / "artifacts/eval_agent_stress/replay.jsonl"
    scenarios = [
        {"id": "direct_rag", "branch": "route/retrieve/grade/generate/verify/respond"},
        {"id": "rewrite_recovery", "branch": "rewrite"},
        {"id": "abstain", "branch": "abstain"},
        {"id": "metadata_tool", "branch": "tool_exec"},
        {"id": "hitl_approve", "branch": "save_report_approve"},
        {"id": "hitl_reject", "branch": "save_report_reject"},
        {"id": "thread_reuse", "branch": "checkpoint_thread_isolation"},
    ]
    replay: list[dict[str, Any]] = []

    runtime = _runtime(root)
    graph = build_agent_graph(runtime)
    direct = graph.invoke(
        initial_state(f"{PROJECT} 사업 예산 알려줘"), run_config("direct")
    )
    replay.append(
        {
            "id": "direct_rag",
            "ok": direct.get("outcome") == "answered"
            and direct.get("rewrite_count") == 0
            and "130,000,000" in direct.get("answer", {}).get("answer", ""),
            "outcome": direct.get("outcome"),
            "rewrite_count": direct.get("rewrite_count"),
        }
    )

    rewrite_runtime = _runtime(root, min_score=0.45)
    rewrite_graph = build_agent_graph(rewrite_runtime)
    noisy = NOISY_PREFIX + f"{PROJECT} 사업 예산 알려줘"
    rewrite_precondition = search(rewrite_runtime.store, noisy, top_k=1)[0].score < 0.45
    rewrite = rewrite_graph.invoke(initial_state(noisy), run_config("rewrite"))
    replay.append(
        {
            "id": "rewrite_recovery",
            "ok": rewrite_precondition
            and rewrite.get("outcome") == "answered"
            and 1 <= rewrite.get("rewrite_count", 0) <= 2,
            "outcome": rewrite.get("outcome"),
            "rewrite_count": rewrite.get("rewrite_count"),
        }
    )

    abstain = graph.invoke(
        initial_state("화성 이주선 산소탱크 발사일은 언제야?"), run_config("abstain")
    )
    replay.append(
        {
            "id": "abstain",
            "ok": abstain.get("outcome") == "abstained"
            and abstain.get("rewrite_count") == 2,
            "outcome": abstain.get("outcome"),
            "rewrite_count": abstain.get("rewrite_count"),
        }
    )

    metadata = graph.invoke(
        initial_state("사업 금액이 가장 큰 공고 1건은?"), run_config("metadata")
    )
    replay.append(
        {
            "id": "metadata_tool",
            "ok": metadata.get("route") == "metadata_query"
            and metadata.get("tool_result", {}).get("doc_ids") == ["doc:000"],
            "outcome": metadata.get("outcome"),
            "route": metadata.get("route"),
        }
    )

    checkpointer = MemorySaver()
    approve_runtime = _runtime(root, thread_id="hitl-approve")
    approve_graph = build_agent_graph(approve_runtime, checkpointer=checkpointer)
    reports_dir = root / "artifacts/eval_agent_stress/reports"
    reports_before_approval = set(reports_dir.glob("*.md"))
    approve_first = approve_graph.invoke(
        initial_state(f"{PROJECT} 사업을 요약해서 보고서로 저장해줘"),
        run_config("hitl-approve"),
    )
    reports_after_interrupt = set(reports_dir.glob("*.md"))
    no_side_effect_before_approval = reports_after_interrupt == reports_before_approval
    approve_resumed = approve_graph.invoke(
        Command(resume="approve"), run_config("hitl-approve")
    )
    replay.append(
        {
            "id": "hitl_approve",
            "ok": "__interrupt__" in approve_first
            and approve_resumed.get("outcome") == "answered"
            and bool(approve_resumed.get("answer", {}).get("report_path")),
            "interrupted": "__interrupt__" in approve_first,
            "outcome": approve_resumed.get("outcome"),
        }
    )

    reject_runtime = _runtime(root, thread_id="hitl-reject")
    reject_graph = build_agent_graph(reject_runtime, checkpointer=MemorySaver())
    reject_first = reject_graph.invoke(
        initial_state(f"{PROJECT} 사업을 요약해서 보고서로 저장해줘"),
        run_config("hitl-reject"),
    )
    reject_resumed = reject_graph.invoke(
        Command(resume="reject"), run_config("hitl-reject")
    )
    replay.append(
        {
            "id": "hitl_reject",
            "ok": "__interrupt__" in reject_first
            and reject_resumed.get("outcome") == "rejected",
            "interrupted": "__interrupt__" in reject_first,
            "outcome": reject_resumed.get("outcome"),
        }
    )

    thread_runtime = _runtime(root, thread_id="thread-reuse")
    thread_graph = build_agent_graph(thread_runtime, checkpointer=MemorySaver())
    config = run_config("thread-reuse")
    first = thread_graph.invoke(
        initial_state("화성 이주선 산소탱크 발사일은 언제야?"), config
    )
    second_question = f"{PROJECT} 사업 예산 알려줘"
    second = thread_graph.invoke(initial_state(second_question), config)
    replay.append(
        {
            "id": "thread_reuse",
            "ok": first.get("outcome") == "abstained"
            and second.get("outcome") == "answered"
            and second.get("answer", {}).get("query") == second_question,
            "first_outcome": first.get("outcome"),
            "second_outcome": second.get("outcome"),
        }
    )

    _write_jsonl(replay_path, replay)
    replay_ok = all(row["ok"] for row in replay)
    metrics = {
        "trajectory_pass_rate": 1.0 if replay_ok else 0.0,
        "branch_coverage": 1.0
        if len({row["id"] for row in replay}) == len(scenarios)
        else 0.0,
        "thread_id_isolation_pass": 1.0 if replay[-1]["ok"] else 0.0,
        "hitl_approval_convergence": 1.0
        if all(row["ok"] for row in replay if row["id"].startswith("hitl_"))
        else 0.0,
        "no_side_effect_before_approval": 1.0
        if no_side_effect_before_approval
        else 0.0,
        "checkpoint_close_path_pass": 1.0 if _checkpoint_close_path_pass(root) else 0.0,
        "audit_arg_redaction_pass": 1.0 if _state_redaction_pass() else 0.0,
        "ops_tool_budget_violation_count": 0 if _tool_budget_pass() else 1,
    }
    thresholds = {
        "trajectory_pass_rate": 1.0,
        "branch_coverage": 1.0,
        "thread_id_isolation_pass": 1.0,
        "hitl_approval_convergence": 1.0,
        "no_side_effect_before_approval": 1.0,
        "checkpoint_close_path_pass": 1.0,
        "audit_arg_redaction_pass": 1.0,
        "ops_tool_budget_violation_count": 0,
    }
    failed = [key for key, threshold in thresholds.items() if metrics[key] != threshold]
    summary = {
        "agent_stress_complete": not failed,
        "scenario_matrix_hash": _scenario_hash(scenarios),
        "branch_replay_artifact_path": "artifacts/eval_agent_stress/replay.jsonl",
        "metrics": metrics,
        "thresholds": thresholds,
        "failed": failed,
        "scenario_count": len(scenarios),
    }
    _write_json(out, summary)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic Stage 2 agent stress checks."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    summary = evaluate_agent_stress(root=args.root, out=args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["agent_stress_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
