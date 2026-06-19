from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.visual_quality import main, write_visual_quality


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_write_visual_quality_records_measured_failure_reasons(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "artifacts/eval/metrics.json",
        {
            "aggregate": {"visual_evidence_hit_rate": 0.92},
            "query_set_counts": {"visual_table": 25},
        },
    )
    _write_json(
        tmp_path / "artifacts/visual_tesseract_candidate_expanded_eval/summary.json",
        {"negative_gold_count": 85, "negative_violation_count": 3},
    )

    summary = write_visual_quality(root=tmp_path)

    assert summary["visual_quality_complete"] is False
    assert summary["metrics"]["visual_question_count"] == 25
    assert summary["metrics"]["visual_evidence_hit_rate"] == 0.92
    assert summary["metrics"]["unsupported_visual_claim_rate"] == 3 / 85
    assert summary["failed"] == [
        "sidecar_abstention_no_regression",
        "sidecar_citation_no_regression",
        "visual_question_count",
    ]


def test_write_visual_quality_passes_when_all_metrics_available(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "artifacts/eval/metrics.json",
        {
            "aggregate": {"visual_evidence_hit_rate": 0.92},
            "query_set_counts": {"visual_table": 30},
        },
    )
    _write_json(
        tmp_path / "artifacts/visual_tesseract_candidate_expanded_eval/summary.json",
        {"negative_gold_count": 85, "negative_violation_count": 3},
    )
    _write_json(
        tmp_path / "artifacts/visual_quality/sidecar_regression.json",
        {
            "sidecar_citation_no_regression": True,
            "sidecar_abstention_no_regression": True,
        },
    )

    summary = write_visual_quality(root=tmp_path)

    assert summary["visual_quality_complete"] is True
    assert summary["failed"] == []


def test_write_visual_quality_prefers_stage2_visual_questions(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "artifacts/eval/metrics.json",
        {
            "aggregate": {"visual_evidence_hit_rate": 0.92},
            "query_set_counts": {"visual_table": 25},
        },
    )
    (tmp_path / "artifacts/eval_stage2").mkdir(parents=True)
    (tmp_path / "artifacts/eval_stage2/visual_table_questions.jsonl").write_text(
        "\n".join(json.dumps({"id": f"v{idx}"}) for idx in range(30)) + "\n",
        encoding="utf-8",
    )

    summary = write_visual_quality(root=tmp_path)

    assert summary["metrics"]["visual_question_count"] == 30
    assert (
        "artifacts/eval_stage2/visual_table_questions.jsonl"
        in summary["measured_sources"]
    )
    assert "visual_question_count" not in summary["failed"]


def test_visual_quality_cli_returns_nonzero_until_complete(tmp_path: Path) -> None:
    rc = main(["--root", str(tmp_path)])

    assert rc == 1
    saved = json.loads(
        (tmp_path / "artifacts/visual_quality/summary.json").read_text(encoding="utf-8")
    )
    assert saved["visual_quality_complete"] is False
