from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.observability_report import evaluate_observability, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_inputs(root: Path) -> None:
    _write_json(
        root / "artifacts/service_ops/summary.json",
        {"metrics": {"latency_p50_ms": 10.0, "latency_p95_ms": 25.0}},
    )
    _write_json(
        root / "artifacts/cost_budget/summary.json",
        {"metrics": {"token_record_coverage": 1.0, "cost_record_coverage": 1.0}},
    )
    _write_jsonl(
        root / "artifacts/eval_agent_stress/replay.jsonl",
        [
            {"id": "rewrite_recovery", "ok": True, "outcome": "answered"},
            {"id": "abstain", "ok": True, "outcome": "abstained"},
            {"id": "hitl_reject", "ok": True, "outcome": "rejected"},
            {"id": "thread_reuse", "ok": True, "second_outcome": "answered"},
        ],
    )
    _write_jsonl(
        root / "artifacts/eval_agent/agent_artifacts/audit.jsonl",
        [{"tool": "search_rfp", "outcome": "ok"}],
    )


def test_evaluate_observability_writes_redacted_trace_and_analysis(
    tmp_path: Path,
) -> None:
    _write_inputs(tmp_path)

    summary = evaluate_observability(root=tmp_path)

    assert summary["observability_complete"] is True
    assert summary["trace_provider"] == "local_redacted_artifact_export"
    assert summary["metrics"]["trace_export_present"] == 1.0
    assert summary["metrics"]["failed_run_analysis_count"] == 5
    trace_text = (tmp_path / "artifacts/observability/traces.jsonl").read_text(
        encoding="utf-8"
    )
    assert "raw_question_and_source_text_omitted" in trace_text
    analysis_text = (tmp_path / "docs/portfolio/failed-run-analysis.md").read_text(
        encoding="utf-8"
    )
    assert "rewrite_recovery" in analysis_text
    assert "raw prompts" in analysis_text


def test_evaluate_observability_fails_closed_without_cost_inputs(
    tmp_path: Path,
) -> None:
    _write_inputs(tmp_path)
    (tmp_path / "artifacts/cost_budget/summary.json").unlink()

    summary = evaluate_observability(root=tmp_path)

    assert summary["observability_complete"] is False
    assert "token_cost_recorded" in summary["failed"]


def test_observability_cli_returns_nonzero_on_failed_summary(tmp_path: Path) -> None:
    rc = main(["--root", str(tmp_path)])

    assert rc == 1
    summary = json.loads(
        (tmp_path / "artifacts/observability/summary.json").read_text(encoding="utf-8")
    )
    assert summary["observability_complete"] is False
