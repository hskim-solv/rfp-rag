from __future__ import annotations

import json
from pathlib import Path

import pytest

from rfp_rag.index_store import SearchResult
from rfp_rag.visual_sidecar import (
    attach_visual_evidence,
    load_reviewed_visual_evidence,
    load_visual_sidecar,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _candidate_rows() -> list[dict]:
    return [
        {
            "record_id": "doc:040:p10:requirements_table",
            "fact_type": "visual_type_present",
            "field": "requirements",
            "value": "Requirements table is present on the selected page",
            "extractor": "visual_tesseract_ocr_candidate_v2",
            "confidence": 0.77,
            "matched_keywords": ["요구사항", "기능", "항목", "구분"],
        },
        {
            "record_id": "doc:071:p3:gantt_schedule",
            "fact_type": "visual_type_present",
            "field": "schedule",
            "value": "Gantt-style project schedule is present on the selected page",
            "extractor": "visual_tesseract_ocr_candidate_v2",
            "confidence": 0.81,
        },
    ]


def test_load_visual_sidecar_groups_gate_passing_candidates_by_doc_id(
    tmp_path: Path,
) -> None:
    candidate_path = tmp_path / "candidate_facts.jsonl"
    gate_path = tmp_path / "gate" / "summary.json"
    _write_jsonl(candidate_path, _candidate_rows())
    _write_json(gate_path, {"decision": "visual_candidate_gate", "ok": True})

    index = load_visual_sidecar(candidate_path, gate_path)

    assert sorted(index.by_doc_id) == ["doc:040", "doc:071"]
    assert index.by_doc_id["doc:040"][0] == {
        "record_id": "doc:040:p10:requirements_table",
        "doc_id": "doc:040",
        "page": 10,
        "visual_type": "requirements_table",
        "fact_type": "visual_type_present",
        "field": "requirements",
        "value": "Requirements table is present on the selected page",
        "extractor": "visual_tesseract_ocr_candidate_v2",
        "confidence": 0.77,
        "matched_keywords": ["요구사항", "기능", "항목", "구분"],
    }


def test_load_reviewed_visual_evidence_uses_only_structured_gold_facts(
    tmp_path: Path,
) -> None:
    records_path = tmp_path / "records.jsonl"
    _write_jsonl(
        records_path,
        [
            {
                "record_id": "doc:040:p10:requirements_table",
                "doc_id": "doc:040",
                "page": 10,
                "visual_type": "requirements_table",
                "structured_facts": [
                    {
                        "fact_id": "doc:040:p10:requirements_table:fact:000",
                        "fact_type": "visual_type_present",
                        "field": "requirements",
                        "value": "Requirements table is present on the selected page",
                        "confidence": 0.9,
                        "reviewer": "manual_page_review_2026_06_16",
                        "evidence_quote": "manual review confirmed a requirements table",
                    }
                ],
            },
            {
                "record_id": "doc:041:p2:requirements_table",
                "doc_id": "doc:041",
                "page": 2,
                "visual_type": "requirements_table",
                "structured_facts": [],
            },
        ],
    )

    index = load_reviewed_visual_evidence(records_path)

    assert sorted(index.by_doc_id) == ["doc:040"]
    assert index.by_doc_id["doc:040"][0] == {
        "record_id": "doc:040:p10:requirements_table",
        "fact_id": "doc:040:p10:requirements_table:fact:000",
        "doc_id": "doc:040",
        "page": 10,
        "visual_type": "requirements_table",
        "fact_type": "visual_type_present",
        "field": "requirements",
        "value": "Requirements table is present on the selected page",
        "confidence": 0.9,
        "reviewer": "manual_page_review_2026_06_16",
        "evidence_quote": "manual review confirmed a requirements table",
        "source": "visual_structure_reviewed",
    }


def test_load_visual_sidecar_rejects_failed_gate(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate_facts.jsonl"
    gate_path = tmp_path / "gate" / "summary.json"
    _write_jsonl(candidate_path, _candidate_rows())
    _write_json(gate_path, {"decision": "visual_candidate_gate", "ok": False})

    with pytest.raises(ValueError, match="visual candidate gate did not pass"):
        load_visual_sidecar(candidate_path, gate_path)


def test_load_visual_sidecar_requires_gate_summary(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate_facts.jsonl"
    _write_jsonl(candidate_path, _candidate_rows())

    with pytest.raises(ValueError, match="visual candidate gate summary is required"):
        load_visual_sidecar(candidate_path)


def test_attach_visual_evidence_copies_results_without_mutating_original(
    tmp_path: Path,
) -> None:
    candidate_path = tmp_path / "candidate_facts.jsonl"
    gate_path = tmp_path / "gate" / "summary.json"
    _write_jsonl(candidate_path, _candidate_rows())
    _write_json(gate_path, {"decision": "visual_candidate_gate", "ok": True})
    index = load_visual_sidecar(candidate_path, gate_path)
    result = SearchResult(
        chunk_id="doc:040:chunk:0",
        doc_id="doc:040",
        csv_row_id="040",
        score=0.9,
        text="본문",
        metadata={"project_name": "사업"},
    )

    attached = attach_visual_evidence([result], index)

    assert "visual_evidence" not in result.metadata
    assert attached[0].metadata["visual_evidence"][0]["record_id"] == (
        "doc:040:p10:requirements_table"
    )
    assert attached[0].metadata["visual_evidence_count"] == 1
