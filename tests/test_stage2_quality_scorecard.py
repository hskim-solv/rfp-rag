from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.stage2_quality_scorecard import build_stage2_quality_scorecard, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_complete_inputs(root: Path) -> None:
    _write_json(
        root / "artifacts/parser_quality/summary.json",
        {
            "doc_count": 100,
            "average_quality_score": 0.95,
            "page_citation_coverage": 1.0,
            "low_quality_doc_count": 0,
        },
    )
    _write_json(
        root / "artifacts/retrieval_bakeoff/summary.json",
        {
            "retrieval_bakeoff_complete": True,
            "metrics": {
                "recall_no_regression": 1.0,
                "citation_validity_no_regression": 1.0,
                "abstention_no_regression": 1.0,
                "section_hit_no_regression": 1.0,
                "visual_evidence_no_regression": 1.0,
                "latency_budget_pass": 1.0,
                "cost_budget_pass": 1.0,
            },
        },
    )
    _write_json(
        root / "artifacts/visual_quality/summary.json",
        {
            "visual_quality_complete": True,
            "metrics": {
                "visual_evidence_hit_rate": 0.95,
                "visual_question_count": 30,
            },
        },
    )
    _write_json(
        root / "artifacts/eval_stage2_real/metrics.json",
        {
            "holdout_quality_complete": True,
            "query_set_counts": {"total": 150},
        },
    )
    _write_json(
        root / "artifacts/eval_stage3_holdout/metrics.json",
        {
            "stage3_holdout_quality_complete": True,
            "metrics": {
                "document_count": 20,
                "query_count": 100,
                "unsupported_visual_claim_rate": 0.0,
                "recall@5": 0.95,
                "mrr": 0.9,
                "faithfulness": 0.9,
                "answer_relevancy": 0.86,
            },
        },
    )
    _write_jsonl(
        root / "artifacts/eval_stage3_raw/predictions.jsonl",
        [
            {
                "expected_doc_ids": ["doc:001"],
                "retrieved_doc_ids": ["doc:001", "doc:001"],
                "pass_fail": {"citation_validity": 1.0},
            },
            {
                "expected_doc_ids": ["doc:002", "doc:003"],
                "retrieved_doc_ids": ["doc:002", "doc:003"],
                "pass_fail": {"citation_validity": 1.0},
            },
        ],
    )


def test_build_stage2_quality_scorecard_accepts_complete_evidence(
    tmp_path: Path,
) -> None:
    _write_complete_inputs(tmp_path)

    summary = build_stage2_quality_scorecard(root=tmp_path)

    assert summary["stage2_quality_scorecard_complete"] is True
    assert summary["failed"] == []
    assert summary["metrics"]["context_precision_at5"] == 1.0
    assert summary["metrics"]["context_recall_at5"] == 1.0
    assert summary["metrics"]["citation_precision_proxy"] == 1.0


def test_build_stage2_quality_scorecard_fails_on_context_precision(
    tmp_path: Path,
) -> None:
    _write_complete_inputs(tmp_path)
    _write_jsonl(
        tmp_path / "artifacts/eval_stage3_raw/predictions.jsonl",
        [
            {
                "expected_doc_ids": ["doc:001"],
                "retrieved_doc_ids": ["doc:999", "doc:998"],
                "pass_fail": {"citation_validity": 0.0},
            }
        ],
    )

    summary = build_stage2_quality_scorecard(root=tmp_path)

    assert summary["stage2_quality_scorecard_complete"] is False
    assert "context_precision_at5" in summary["failed"]
    assert "context_recall_at5" in summary["failed"]
    assert "citation_precision_proxy" in summary["failed"]


def test_stage2_quality_scorecard_cli_writes_summary(tmp_path: Path) -> None:
    _write_complete_inputs(tmp_path)
    out = tmp_path / "out/summary.json"

    rc = main(["--root", str(tmp_path), "--out", str(out)])

    assert rc == 0
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["stage2_quality_scorecard_complete"] is True
