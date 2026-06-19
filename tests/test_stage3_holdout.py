from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.stage3_holdout import audit_stage3_cases, finalize_stage3_holdout, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _cases(doc_count: int = 20, query_count: int = 100) -> list[dict]:
    rows: list[dict] = []
    for i in range(query_count):
        doc_id = f"stage3-doc-{i % doc_count:03d}"
        rows.append(
            {
                "id": f"stage3-{i:03d}",
                "query": f"독립 평가 질문 {i}",
                "query_type": "text" if i % 5 else "abstention",
                "expected_doc_ids": [doc_id],
                "label_source": "manual_blind_label",
                "provenance": {
                    "corpus_split": "stage3_independent_holdout",
                    "stage2_overlap": False,
                },
            }
        )
    return rows


def _raw_metrics() -> dict:
    return {
        "metrics": {
            "recall@5": 0.90,
            "mrr": 0.80,
            "citation_validity": 0.95,
            "faithfulness": 0.85,
            "answer_relevancy": 0.78,
            "unsupported_visual_claim_rate": 0.05,
            "abstention_precision": 0.90,
        }
    }


def test_audit_stage3_cases_accepts_independent_fixed_set(tmp_path: Path) -> None:
    cases_path = tmp_path / "eval_sets/stage3_holdout/cases.jsonl"
    _write_jsonl(cases_path, _cases())

    audit = audit_stage3_cases(root=tmp_path)

    assert audit["stage3_case_audit_complete"] is True
    assert audit["metrics"]["document_count"] == 20
    assert audit["metrics"]["query_count"] == 100
    assert audit["failed"] == []
    assert len(audit["eval_set_hash"]) == 64


def test_audit_stage3_cases_allows_abstention_without_expected_docs(
    tmp_path: Path,
) -> None:
    rows = _cases()
    rows[0]["query_type"] = "abstention"
    rows[0]["expected_doc_ids"] = []
    rows[0]["required_phrase"] = "없는 정보"
    rows[0]["required_warning"] = "insufficient_context"
    cases_path = tmp_path / "eval_sets/stage3_holdout/cases.jsonl"
    _write_jsonl(cases_path, rows)

    audit = audit_stage3_cases(root=tmp_path)

    assert audit["stage3_case_audit_complete"] is True
    assert audit["failed"] == []


def test_finalize_stage3_holdout_accepts_complete_raw_metrics(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "eval_sets/stage3_holdout/cases.jsonl", _cases())
    _write_json(tmp_path / "artifacts/eval_stage3_raw/metrics.json", _raw_metrics())

    summary = finalize_stage3_holdout(root=tmp_path)

    assert summary["stage3_holdout_quality_complete"] is True
    assert summary["contract_version"] == "rfp-rag-stage3-holdout-v1"
    assert summary["metrics"]["document_count"] == 20
    assert summary["metrics"]["query_count"] == 100
    assert summary["failed"] == []
    assert (tmp_path / "artifacts/eval_stage3_holdout/split_manifest.json").is_file()
    assert (tmp_path / "artifacts/eval_stage3_holdout/label_rubric.md").is_file()


def test_finalize_stage3_holdout_fails_closed_without_raw_metrics(
    tmp_path: Path,
) -> None:
    _write_jsonl(tmp_path / "eval_sets/stage3_holdout/cases.jsonl", _cases())

    summary = finalize_stage3_holdout(root=tmp_path)

    assert summary["stage3_holdout_quality_complete"] is False
    assert "stage3_real_metrics_missing" in summary["failed"]
    assert "recall@5" in summary["failed"]


def test_stage3_holdout_cli_returns_nonzero_when_cases_are_missing(
    tmp_path: Path,
) -> None:
    rc = main(["--root", str(tmp_path)])

    assert rc == 1
    summary = json.loads(
        (tmp_path / "artifacts/eval_stage3_holdout/metrics.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["stage3_holdout_quality_complete"] is False
    assert "cases_missing" in summary["failed"]
