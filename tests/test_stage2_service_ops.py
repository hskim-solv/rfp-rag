from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rfp_rag import stage2_service_ops
from rfp_rag.stage2_service_ops import evaluate_service_ops, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_ops_inputs(root: Path) -> None:
    _write_json(
        root / "artifacts/eval/metrics.json",
        {"provider_lane": "offline", "aggregate": {"recall@5": 1.0}},
    )
    _write_jsonl(
        root / "artifacts/eval/predictions.jsonl",
        [{"query": "질문", "source_texts": ["근거"], "answer": "답변", "warnings": []}],
    )
    _write_jsonl(
        root / "artifacts/eval_agent/agent_artifacts/audit.jsonl",
        [{"tool": "search_rfp", "outcome": "ok", "approved": None}],
    )


def test_evaluate_service_ops_writes_measured_summary(
    tmp_path: Path, monkeypatch
) -> None:
    _write_ops_inputs(tmp_path)

    def fake_answer_query(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "answer": "근거 기반 답변",
            "confidence": "high",
            "warnings": [],
            "sources": [],
            "retrieved_doc_ids": [],
            "retrieved_chunk_ids": [],
            "scores": [],
            "reranker": "none",
            "rerank_candidate_k": 5,
        }

    monkeypatch.setattr(
        stage2_service_ops.service_app, "answer_query", fake_answer_query
    )
    monkeypatch.setattr(
        stage2_service_ops.service_app,
        "collect_gate_status",
        lambda root: {"overall_ok": False, "root": str(root)},
    )

    summary = evaluate_service_ops(root=tmp_path, full_answer=True)

    assert summary["service_ops_complete"] is True
    assert summary["metrics"]["healthz_pass"] == 1.0
    assert summary["metrics"]["answer_pass"] == 1.0
    assert summary["metrics"]["stream_pass"] == 1.0
    assert summary["metrics"]["gates_pass"] == 1.0
    assert summary["metrics"]["ops_summary_pass"] == 1.0
    assert summary["metrics"]["path_safety_pass"] == 1.0
    assert summary["metrics"]["token_cost_distribution_recorded"] == 1.0
    assert summary["failed"] == []
    saved = json.loads(
        (tmp_path / "artifacts/service_ops/summary.json").read_text(encoding="utf-8")
    )
    assert saved == summary


def test_stage2_service_ops_cli_returns_nonzero_on_failed_smoke(
    tmp_path: Path, monkeypatch
) -> None:
    _write_ops_inputs(tmp_path)

    def failing_answer_query(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        stage2_service_ops.service_app, "answer_query", failing_answer_query
    )

    rc = main(["--root", str(tmp_path), "--full-answer"])

    assert rc == 1
    summary = json.loads(
        (tmp_path / "artifacts/service_ops/summary.json").read_text(encoding="utf-8")
    )
    assert summary["service_ops_complete"] is False
    assert "answer_pass" in summary["failed"]
