from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.visual_structure import (
    build_visual_structure_records,
    parse_manual_review_markdown,
    run_visual_structure_extraction,
    write_visual_structure_artifacts,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _review_markdown() -> str:
    return """# Visual audit manual review

## Per-document findings

| Rank | doc_id | Visual elements | Visual-only risk | Affected fields | Recommendation |
|---:|---|---|---|---|---|
| 1 | `doc:001` | Gantt schedule, project organization chart, requirements summary/list tables | yes | schedule, requirements | adopt now |
| 2 | `doc:002` | dashboard screenshots, target service model | uncertain | requirements, system architecture | inspect individual page |
| 3 | `doc:003` | overview tables | no | none | defer |
"""


def _samples() -> list[dict]:
    return [
        {
            "rank": 1,
            "doc_id": "doc:001",
            "source_filename": "a.hwp",
            "pdf_path": "/tmp/doc_001.pdf",
            "page_text_path": "/tmp/doc_001.jsonl",
            "selected_pages": [3, 4],
            "audit_reasons": ["chart_or_drawing_signal_present"],
        },
        {
            "rank": 2,
            "doc_id": "doc:002",
            "source_filename": "b.pdf",
            "pdf_path": "/tmp/doc_002.pdf",
            "page_text_path": "/tmp/doc_002.jsonl",
            "selected_pages": [5],
            "audit_reasons": ["image_signal_present"],
        },
        {
            "rank": 3,
            "doc_id": "doc:003",
            "source_filename": "c.pdf",
            "pdf_path": "/tmp/doc_003.pdf",
            "page_text_path": "/tmp/doc_003.jsonl",
            "selected_pages": [1],
            "audit_reasons": ["table_signal_loss"],
        },
    ]


def test_parse_manual_review_markdown_extracts_findings(tmp_path: Path) -> None:
    review = tmp_path / "review.md"
    review.write_text(_review_markdown(), encoding="utf-8")

    findings = parse_manual_review_markdown(review)

    assert [row["doc_id"] for row in findings] == ["doc:001", "doc:002", "doc:003"]
    assert findings[0]["visual_only_risk"] == "yes"
    assert findings[0]["business_fields"] == ["schedule", "requirements"]
    assert findings[1]["recommendation"] == "inspect individual page"
    assert findings[2]["business_fields"] == []


def test_build_visual_structure_records_links_pages_fields_and_evidence(
    tmp_path: Path,
) -> None:
    review = tmp_path / "review.md"
    review.write_text(_review_markdown(), encoding="utf-8")
    findings = parse_manual_review_markdown(review)

    records, summary = build_visual_structure_records(
        _samples(),
        findings,
        review_path=review,
    )

    assert summary["record_count"] == 8
    assert summary["skipped_no_risk_count"] == 1
    assert summary["business_field_counts"] == {
        "requirements": 8,
        "schedule": 6,
        "system_architecture": 2,
    }
    first = records[0]
    assert first == {
        "record_id": "doc:001:p3:gantt_schedule",
        "doc_id": "doc:001",
        "page": 3,
        "visual_type": "gantt_schedule",
        "business_fields": ["schedule", "requirements"],
        "structured_facts": [],
        "evidence_ref": {
            "pdf_path": "/tmp/doc_001.pdf",
            "page_text_path": "/tmp/doc_001.jsonl",
            "source_filename": "a.hwp",
            "manual_review_path": str(review),
        },
        "extractor": "manual_review_seed_v1",
        "confidence": 0.7,
        "review_status": "reviewed_needs_extraction",
        "source_visual_elements": (
            "Gantt schedule, project organization chart, "
            "requirements summary/list tables"
        ),
        "source_recommendation": "adopt now",
    }
    assert {record["visual_type"] for record in records} == {
        "dashboard_screenshot",
        "gantt_schedule",
        "organization_chart",
        "requirements_table",
        "system_architecture_diagram",
    }


def test_write_visual_structure_artifacts_writes_jsonl_summary_and_review_queue(
    tmp_path: Path,
) -> None:
    records, summary = build_visual_structure_records(
        _samples(),
        parse_manual_review_markdown_text(_review_markdown()),
        review_path=tmp_path / "manual.md",
    )

    write_visual_structure_artifacts(records, summary, tmp_path / "visual_structure")

    assert (tmp_path / "visual_structure" / "records.jsonl").is_file()
    saved_summary = json.loads(
        (tmp_path / "visual_structure" / "summary.json").read_text(encoding="utf-8")
    )
    assert saved_summary["record_count"] == len(records)
    review_queue = (tmp_path / "visual_structure" / "review_queue.md").read_text(
        encoding="utf-8"
    )
    assert "doc:001" in review_queue
    assert "gantt_schedule" in review_queue


def parse_manual_review_markdown_text(markdown: str) -> list[dict]:
    path = Path("/tmp/visual-structure-review-test.md")
    path.write_text(markdown, encoding="utf-8")
    return parse_manual_review_markdown(path)


def test_run_visual_structure_extraction_reads_audit_and_review_inputs(
    tmp_path: Path,
) -> None:
    audit_dir = tmp_path / "visual_audit"
    _write_jsonl(audit_dir / "samples.jsonl", _samples())
    review = tmp_path / "review.md"
    review.write_text(_review_markdown(), encoding="utf-8")

    summary = run_visual_structure_extraction(
        audit_dir=audit_dir,
        review_path=review,
        out_dir=tmp_path / "out",
    )

    assert summary["record_count"] == 8
    assert summary["decision"] == "targeted_visual_structure_extraction_seed"
    first_record = json.loads(
        (tmp_path / "out" / "records.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert first_record["record_id"] == "doc:001:p3:gantt_schedule"
