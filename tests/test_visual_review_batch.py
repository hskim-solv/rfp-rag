from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.visual_facts import merge_visual_facts
from rfp_rag.visual_review_batch import (
    build_visual_review_batch,
    run_visual_review_batch,
)


def _records() -> list[dict]:
    return [
        {
            "record_id": "doc:001:p1:gantt_schedule",
            "doc_id": "doc:001",
            "page": 1,
            "visual_type": "gantt_schedule",
            "business_fields": ["schedule"],
            "structured_facts": [],
            "review_status": "reviewed_needs_extraction",
            "confidence": 0.7,
            "evidence_ref": {"pdf_path": "doc001.pdf"},
        },
        {
            "record_id": "doc:002:p2:dashboard_screenshot",
            "doc_id": "doc:002",
            "page": 2,
            "visual_type": "dashboard_screenshot",
            "business_fields": ["requirements"],
            "structured_facts": [],
            "review_status": "needs_page_review",
            "confidence": 0.5,
            "evidence_ref": {"pdf_path": "doc002.pdf"},
        },
        {
            "record_id": "doc:003:p3:requirements_table",
            "doc_id": "doc:003",
            "page": 3,
            "visual_type": "requirements_table",
            "business_fields": ["requirements"],
            "structured_facts": [],
            "review_status": "needs_page_review",
            "confidence": 0.5,
            "evidence_ref": {"pdf_path": "doc003.pdf"},
        },
        {
            "record_id": "doc:004:p4:organization_chart",
            "doc_id": "doc:004",
            "page": 4,
            "visual_type": "organization_chart",
            "business_fields": ["requirements"],
            "structured_facts": [],
            "review_status": "needs_page_review",
            "confidence": 0.5,
            "evidence_ref": {"pdf_path": "doc004.pdf"},
        },
    ]


def _facts() -> list[dict]:
    return [
        {
            "record_id": "doc:003:p3:requirements_table",
            "fact_type": "visual_type_present",
            "field": "requirements",
            "value": "requirements table is not accepted",
            "reviewer": "reviewer_a",
            "status": "rejected",
            "confidence": 0.8,
        }
    ]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def test_build_visual_review_batch_selects_unresolved_page_review_records() -> None:
    records, facts_template, summary = build_visual_review_batch(
        _records(),
        _facts(),
        review_status="needs_page_review",
        max_records=2,
    )

    assert [record["record_id"] for record in records] == [
        "doc:002:p2:dashboard_screenshot",
        "doc:004:p4:organization_chart",
    ]
    assert [
        (fact["record_id"], fact["fact_type"], fact["field"], fact["status"])
        for fact in facts_template
    ] == [
        (
            "doc:002:p2:dashboard_screenshot",
            "visual_type_present",
            "requirements",
            "needs_review",
        ),
        (
            "doc:004:p4:organization_chart",
            "visual_type_present",
            "requirements",
            "needs_review",
        ),
    ]
    assert summary["decision"] == "visual_gold_review_batch"
    assert summary["source_record_count"] == 4
    assert summary["existing_fact_record_count"] == 1
    assert summary["selected_record_count"] == 2
    assert summary["review_status_filter"] == "needs_page_review"
    assert summary["selected_visual_type_counts"] == {
        "dashboard_screenshot": 1,
        "organization_chart": 1,
    }


def test_build_visual_review_batch_uses_visual_type_default_field() -> None:
    records, facts_template, _summary = build_visual_review_batch(
        [
            {
                "record_id": "doc:071:p3:gantt_schedule",
                "doc_id": "doc:071",
                "page": 3,
                "visual_type": "gantt_schedule",
                "business_fields": ["system_architecture", "requirements"],
                "structured_facts": [],
                "review_status": "needs_page_review",
                "confidence": 0.5,
                "evidence_ref": {"pdf_path": "doc071.pdf"},
            }
        ],
        [],
        review_status="needs_page_review",
    )

    assert records[0]["record_id"] == "doc:071:p3:gantt_schedule"
    assert facts_template[0]["field"] == "schedule"


def test_visual_review_batch_fact_template_matches_review_contract() -> None:
    records, facts_template, _summary = build_visual_review_batch(
        _records(),
        [],
        review_status="needs_page_review",
    )

    _merged_records, summary = merge_visual_facts(records, facts_template)

    assert summary["needs_review_fact_count"] == 3
    assert summary["accepted_fact_count"] == 0


def test_run_visual_review_batch_writes_artifacts(tmp_path: Path) -> None:
    records_path = tmp_path / "records.jsonl"
    facts_path = tmp_path / "facts.jsonl"
    out_dir = tmp_path / "batch"
    _write_jsonl(records_path, _records())
    _write_jsonl(facts_path, _facts())

    summary = run_visual_review_batch(
        records_path=records_path,
        facts_path=facts_path,
        out_dir=out_dir,
        review_status="needs_page_review",
    )

    assert summary["selected_record_count"] == 2
    assert (out_dir / "records.jsonl").is_file()
    assert (out_dir / "facts_template.jsonl").is_file()
    assert (out_dir / "summary.json").is_file()
    review_queue = (out_dir / "review_queue.md").read_text(encoding="utf-8")
    assert "Visual Gold Review Batch" in review_queue
    assert "doc002.pdf" in review_queue


def test_run_visual_review_batch_cli_writes_outputs(tmp_path: Path, capsys) -> None:
    from rfp_rag.run_visual_review_batch import main

    records_path = tmp_path / "records.jsonl"
    facts_path = tmp_path / "facts.jsonl"
    out_dir = tmp_path / "batch"
    _write_jsonl(records_path, _records())
    _write_jsonl(facts_path, _facts())

    assert (
        main(
            [
                "--records",
                str(records_path),
                "--facts",
                str(facts_path),
                "--out",
                str(out_dir),
                "--review-status",
                "needs_page_review",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["selected_record_count"] == 2
    assert (out_dir / "facts_template.jsonl").is_file()
