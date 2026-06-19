from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.portfolio_check import collect_portfolio_readiness
from rfp_rag.stage2_scaffold import main, write_stage2_scaffold


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _rows(count: int, *, prefix: str) -> list[dict]:
    return [
        {"id": f"{prefix}_{idx:03d}", "query": f"{prefix} question {idx}"}
        for idx in range(count)
    ]


def _metadata_rows(doc_count: int, questions_per_doc: int = 4) -> list[dict]:
    rows: list[dict] = []
    for doc_idx in range(doc_count):
        for question_idx in range(questions_per_doc):
            rows.append(
                {
                    "id": f"metadata_{doc_idx:03d}_{question_idx}",
                    "query": f"metadata question {doc_idx} {question_idx}",
                    "expected_doc_ids": [f"doc:{doc_idx:03d}"],
                }
            )
    return rows


def _write_eval_inputs(root: Path) -> None:
    eval_dir = root / "artifacts/eval"
    _write_jsonl(
        eval_dir / "golden_metadata.jsonl", _metadata_rows(100, questions_per_doc=1)
    )
    _write_jsonl(eval_dir / "curated_text_questions.jsonl", _rows(10, prefix="curated"))
    _write_jsonl(
        eval_dir / "section_lookup_questions.jsonl", _rows(30, prefix="section")
    )
    _write_jsonl(eval_dir / "cross_document_questions.jsonl", _rows(20, prefix="cross"))
    _write_jsonl(eval_dir / "visual_table_questions.jsonl", _rows(25, prefix="visual"))
    _write_jsonl(
        eval_dir / "paraphrase_questions.jsonl", _rows(30, prefix="paraphrase")
    )
    _write_jsonl(
        eval_dir / "abstention_questions.jsonl", _rows(30, prefix="abstention")
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_write_stage2_scaffold_creates_contract_artifacts_fail_closed(
    tmp_path: Path,
) -> None:
    _write_eval_inputs(tmp_path)

    summary = write_stage2_scaffold(root=tmp_path)

    assert summary["stage2_scaffold_complete"] is True
    assert summary["artifact_count"] == 8
    coverage = json.loads(
        (tmp_path / "artifacts/eval_stage2/coverage.json").read_text(encoding="utf-8")
    )
    assert len(coverage["eval_set_hash"]) == 64
    assert coverage["metrics"] == {
        "cross_document_count": 20,
        "hard_negative_count": 30,
        "metadata_doc_coverage": 100,
        "query_count": 245,
        "visual_table_count": 25,
    }
    assert coverage["eval_set_audit_complete"] is False
    assert "visual_table_count" in coverage["failed"]

    readiness = collect_portfolio_readiness(tmp_path)
    assert readiness["stage2_contract_schema_enforced"] is False
    assert readiness["second_stage_readiness"]["missing"] == []
    assert "eval_stage2_coverage" in readiness["second_stage_readiness"]["failed"]
    assert "eval_stage2_real" in readiness["second_stage_readiness"]["failed"]


def test_write_stage2_scaffold_populates_visual_quality_from_existing_metrics(
    tmp_path: Path,
) -> None:
    _write_eval_inputs(tmp_path)
    _write_json(
        tmp_path / "artifacts/eval/metrics.json",
        {
            "aggregate": {"visual_evidence_hit_rate": 0.92},
            "query_set_counts": {"visual_table": 25},
        },
    )
    _write_json(
        tmp_path / "artifacts/visual_tesseract_candidate_expanded_eval/summary.json",
        {
            "negative_gold_count": 85,
            "negative_violation_count": 3,
        },
    )

    write_stage2_scaffold(root=tmp_path)

    visual = json.loads(
        (tmp_path / "artifacts/visual_quality/summary.json").read_text(encoding="utf-8")
    )
    assert visual["metrics"]["visual_question_count"] == 25
    assert visual["metrics"]["visual_evidence_hit_rate"] == 0.92
    assert visual["metrics"]["unsupported_visual_claim_rate"] == 3 / 85
    assert visual["metrics"]["sidecar_citation_no_regression"] == 0.0
    assert visual["visual_quality_complete"] is False
    assert visual["measured_sources"] == [
        "artifacts/eval/metrics.json",
        "artifacts/visual_tesseract_candidate_expanded_eval/summary.json",
    ]


def test_write_stage2_scaffold_counts_metadata_unique_doc_coverage(
    tmp_path: Path,
) -> None:
    _write_eval_inputs(tmp_path)
    _write_jsonl(
        tmp_path / "artifacts/eval/golden_metadata.jsonl",
        _metadata_rows(100, questions_per_doc=4),
    )

    write_stage2_scaffold(root=tmp_path)

    coverage = json.loads(
        (tmp_path / "artifacts/eval_stage2/coverage.json").read_text(encoding="utf-8")
    )
    assert coverage["counts_by_slice"]["metadata"] == 400
    assert coverage["metrics"]["metadata_doc_coverage"] == 100


def test_write_stage2_scaffold_prefers_stage2_visual_questions(
    tmp_path: Path,
) -> None:
    _write_eval_inputs(tmp_path)
    _write_jsonl(
        tmp_path / "artifacts/eval_stage2/visual_table_questions.jsonl",
        _rows(30, prefix="stage2_visual"),
    )

    write_stage2_scaffold(root=tmp_path)

    coverage = json.loads(
        (tmp_path / "artifacts/eval_stage2/coverage.json").read_text(encoding="utf-8")
    )
    assert coverage["source_files"]["visual_table"] == (
        "artifacts/eval_stage2/visual_table_questions.jsonl"
    )
    assert coverage["counts_by_slice"]["visual_table"] == 30
    assert coverage["metrics"]["visual_table_count"] == 30
    assert "visual_table_count" not in coverage["failed"]


def test_write_stage2_scaffold_preserves_completed_measured_gate(
    tmp_path: Path,
) -> None:
    _write_eval_inputs(tmp_path)
    service_ops = {
        "service_ops_complete": True,
        "docker_demo_command": "uv run python -m rfp_rag.stage2_service_ops",
        "metrics": {
            "healthz_pass": 1.0,
            "answer_pass": 1.0,
            "stream_pass": 1.0,
            "gates_pass": 1.0,
            "ops_summary_pass": 1.0,
            "path_safety_pass": 1.0,
            "latency_p50_ms": 10.0,
            "latency_p95_ms": 20.0,
            "token_cost_distribution_recorded": 1.0,
        },
        "thresholds": {
            "healthz_pass": 1.0,
            "answer_pass": 1.0,
            "stream_pass": 1.0,
            "gates_pass": 1.0,
            "ops_summary_pass": 1.0,
            "path_safety_pass": 1.0,
            "latency_p50_ms": 0.0,
            "latency_p95_ms": 0.0,
            "token_cost_distribution_recorded": 1.0,
        },
        "failed": [],
    }
    _write_json(tmp_path / "artifacts/service_ops/summary.json", service_ops)

    write_stage2_scaffold(root=tmp_path)

    saved = json.loads(
        (tmp_path / "artifacts/service_ops/summary.json").read_text(encoding="utf-8")
    )
    assert saved == service_ops


def test_write_stage2_scaffold_preserves_measured_failure_gate(
    tmp_path: Path,
) -> None:
    _write_eval_inputs(tmp_path)
    measured_failure = {
        "retrieval_bakeoff_complete": False,
        "decision": "keep_vector_until_candidate_wins",
        "comparison_set_hash": "set-a",
        "compared_modes": ["vector", "hybrid_rrf"],
        "decision_adr_path": "docs/adr/0020-retrieval-bakeoff.md",
        "metrics": {
            "recall_no_regression": 1.0,
            "citation_validity_no_regression": 1.0,
            "abstention_no_regression": 0.0,
            "section_hit_no_regression": 1.0,
            "visual_evidence_no_regression": 1.0,
            "latency_budget_pass": 1.0,
            "cost_budget_pass": 1.0,
        },
        "thresholds": {
            "recall_no_regression": 1.0,
            "citation_validity_no_regression": 1.0,
            "abstention_no_regression": 1.0,
            "section_hit_no_regression": 1.0,
            "visual_evidence_no_regression": 1.0,
            "latency_budget_pass": 1.0,
            "cost_budget_pass": 1.0,
        },
        "failed": ["abstention_no_regression", "missing_modes"],
    }
    _write_json(tmp_path / "artifacts/retrieval_bakeoff/summary.json", measured_failure)

    write_stage2_scaffold(root=tmp_path)

    saved = json.loads(
        (tmp_path / "artifacts/retrieval_bakeoff/summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved == measured_failure


def test_stage2_scaffold_cli_writes_summary(tmp_path: Path, capsys) -> None:
    _write_eval_inputs(tmp_path)

    rc = main(["--root", str(tmp_path)])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stage2_scaffold_complete"] is True
    assert (tmp_path / "artifacts/stage2_scaffold/summary.json").is_file()
