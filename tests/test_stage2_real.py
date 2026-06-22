from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.stage2_real import finalize_stage2_real, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_coverage(root: Path, eval_set_hash: str = "stage2-hash") -> None:
    _write_json(
        root / "artifacts/eval_stage2/coverage.json",
        {
            "eval_set_hash": eval_set_hash,
            "eval_set_audit_complete": True,
            "counts_by_slice": {
                "metadata": 400,
                "curated_text": 10,
                "section_lookup": 30,
                "cross_document": 20,
                "visual_table": 30,
                "paraphrase": 30,
                "abstention": 30,
            },
            "metrics": {},
            "thresholds": {},
            "failed": [],
        },
    )


def _write_small_coverage(root: Path, eval_set_hash: str = "stage2-hash") -> None:
    _write_json(
        root / "artifacts/eval_stage2/coverage.json",
        {
            "eval_set_hash": eval_set_hash,
            "eval_set_audit_complete": True,
            "counts_by_slice": {
                "metadata": 1,
                "curated_text": 1,
                "section_lookup": 1,
                "cross_document": 1,
                "visual_table": 1,
                "paraphrase": 1,
                "abstention": 1,
            },
            "metrics": {},
            "thresholds": {},
            "failed": [],
        },
    )


def _write_complete_predictions(root: Path) -> None:
    rows = [
        ("metadata_budget_000", "project_budget"),
        ("curated_000", "curated_text"),
        ("section_000", "section_lookup"),
        ("cross_000", "cross_document"),
        ("visual_000", "visual_table"),
        ("paraphrase_000", "paraphrase"),
        ("abstention_000", "abstention"),
    ]
    path = root / "artifacts/eval_stage2_real/predictions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    payloads = []
    for query_id, query_type in rows:
        judge = (
            {"warnings": ["judge_skipped_abstention"]}
            if query_type == "abstention"
            else {"faithfulness": 1.0, "answer_relevancy": 1.0, "warnings": []}
        )
        payloads.append(
            json.dumps(
                {"query_id": query_id, "query_type": query_type, "judge": judge},
                ensure_ascii=False,
            )
        )
    path.write_text("\n".join(payloads) + "\n", encoding="utf-8")


def _raw_metrics(**overrides: object) -> dict:
    aggregate = {
        "recall@5": 0.97,
        "recall@3": 0.93,
        "mrr": 0.9,
        "metadata_exact_match": 0.96,
        "faithfulness": 0.96,
        "answer_relevancy": 0.89,
        "judge_coverage_faithfulness": 1.0,
        "judge_coverage_answer_relevancy": 1.0,
        "citation_presence": 1.0,
        "citation_validity": 1.0,
    }
    aggregate.update(overrides.pop("aggregate", {}))
    payload = {
        "provider_lane": "real_openai",
        "generation_model_id": "gpt-test",
        "judge_model_id": "judge-test",
        "embedding_model_id": "embed-test",
        "prompt_template_hash": "a" * 64,
        "evaluation_valid": True,
        "eval_set_hash": "stage2-hash",
        "query_set_counts": {
            "total": 550,
            "golden_metadata": 400,
            "curated_text": 10,
            "section_lookup": 30,
            "cross_document": 20,
            "visual_table": 30,
            "paraphrase": 30,
            "abstention": 30,
        },
        "aggregate": aggregate,
        "per_type": {},
    }
    payload.update(overrides)
    return payload


def test_finalize_stage2_real_writes_passing_contract_artifact(tmp_path: Path) -> None:
    _write_small_coverage(tmp_path)
    _write_complete_predictions(tmp_path)
    _write_json(
        tmp_path / "artifacts/eval_stage2_real/metrics.json",
        _raw_metrics(
            query_set_counts={
                "total": 7,
                "golden_metadata": 1,
                "curated_text": 1,
                "section_lookup": 1,
                "cross_document": 1,
                "visual_table": 1,
                "paraphrase": 1,
                "abstention": 1,
            }
        ),
    )

    summary = finalize_stage2_real(root=tmp_path)

    assert summary["holdout_quality_complete"] is True
    assert summary["eval_set_hash"] == "stage2-hash"
    assert summary["thresholds_met"] is True
    assert summary["per_slice_failed"] == []
    assert summary["metrics"]["recall@5"] == 0.97
    assert (
        summary["metrics"]["judge_coverage_faithfulness_min_by_answerable_slice"] == 1.0
    )
    assert summary["failed"] == []
    saved = json.loads(
        (tmp_path / "artifacts/eval_stage2_real/metrics.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved["holdout_quality_complete"] is True


def test_finalize_stage2_real_is_idempotent_after_contract_write(
    tmp_path: Path,
) -> None:
    _write_small_coverage(tmp_path)
    _write_complete_predictions(tmp_path)
    _write_json(
        tmp_path / "artifacts/eval_stage2_real/metrics.json",
        _raw_metrics(
            query_set_counts={
                "total": 7,
                "golden_metadata": 1,
                "curated_text": 1,
                "section_lookup": 1,
                "cross_document": 1,
                "visual_table": 1,
                "paraphrase": 1,
                "abstention": 1,
            }
        ),
    )

    first = finalize_stage2_real(root=tmp_path)
    second = finalize_stage2_real(root=tmp_path)

    assert first["holdout_quality_complete"] is True
    assert second["holdout_quality_complete"] is True
    assert second["failed"] == []


def test_finalize_stage2_real_fails_closed_when_lineage_is_missing(
    tmp_path: Path,
) -> None:
    _write_coverage(tmp_path)
    raw = _raw_metrics(generation_model_id="")
    _write_json(tmp_path / "artifacts/eval_stage2_real/metrics.json", raw)

    summary = finalize_stage2_real(root=tmp_path)

    assert summary["holdout_quality_complete"] is False
    assert "generation_model_id" in summary["failed"]


def test_finalize_stage2_real_fails_closed_when_thresholds_miss(
    tmp_path: Path,
) -> None:
    _write_coverage(tmp_path)
    _write_json(
        tmp_path / "artifacts/eval_stage2_real/metrics.json",
        _raw_metrics(aggregate={"faithfulness": 0.8}),
    )

    summary = finalize_stage2_real(root=tmp_path)

    assert summary["holdout_quality_complete"] is False
    assert summary["thresholds_met"] is False
    assert "faithfulness" in summary["failed"]
    assert "faithfulness" in summary["per_slice_failed"]


def test_finalize_stage2_real_fails_closed_when_query_set_counts_mismatch(
    tmp_path: Path,
) -> None:
    _write_coverage(tmp_path)
    raw = _raw_metrics(query_set_counts={"total": 545})
    _write_json(tmp_path / "artifacts/eval_stage2_real/metrics.json", raw)

    summary = finalize_stage2_real(root=tmp_path)

    assert summary["holdout_quality_complete"] is False
    assert "query_set_counts.total" in summary["failed"]


def test_finalize_stage2_real_fails_closed_when_raw_hash_mismatches(
    tmp_path: Path,
) -> None:
    _write_coverage(tmp_path, eval_set_hash="stage2-hash")
    raw = _raw_metrics(eval_set_hash="different-hash")
    _write_json(tmp_path / "artifacts/eval_stage2_real/metrics.json", raw)

    summary = finalize_stage2_real(root=tmp_path)

    assert summary["holdout_quality_complete"] is False
    assert "eval_set_hash" in summary["failed"]


def test_stage2_real_cli_returns_nonzero_until_contract_passes(tmp_path: Path) -> None:
    rc = main(["--root", str(tmp_path)])

    assert rc == 1
    saved = json.loads(
        (tmp_path / "artifacts/eval_stage2_real/metrics.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved["holdout_quality_complete"] is False
