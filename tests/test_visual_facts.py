from __future__ import annotations

import json
from pathlib import Path

import pytest

from rfp_rag.visual_facts import (
    merge_visual_facts,
    run_visual_fact_review,
    write_visual_fact_artifacts,
)


def _records() -> list[dict]:
    return [
        {
            "record_id": "doc:001:p3:gantt_schedule",
            "doc_id": "doc:001",
            "page": 3,
            "visual_type": "gantt_schedule",
            "business_fields": ["schedule", "requirements"],
            "structured_facts": [],
            "review_status": "reviewed_needs_extraction",
            "confidence": 0.7,
            "evidence_ref": {"pdf_path": "doc001.pdf"},
        },
        {
            "record_id": "doc:002:p5:system_architecture_diagram",
            "doc_id": "doc:002",
            "page": 5,
            "visual_type": "system_architecture_diagram",
            "business_fields": ["system_architecture", "requirements"],
            "structured_facts": [],
            "review_status": "needs_page_review",
            "confidence": 0.5,
            "evidence_ref": {"pdf_path": "doc002.pdf"},
        },
    ]


def _facts() -> list[dict]:
    return [
        {
            "record_id": "doc:001:p3:gantt_schedule",
            "fact_type": "visual_type_present",
            "field": "schedule",
            "value": "Gantt schedule is present on page 3",
            "evidence_quote": "manual page review",
            "reviewer": "reviewer_a",
            "status": "accepted",
            "confidence": 0.9,
        },
        {
            "record_id": "doc:001:p3:gantt_schedule",
            "fact_type": "schedule_milestone",
            "field": "schedule",
            "value": "Kickoff milestone",
            "evidence_quote": "착수",
            "reviewer": "reviewer_a",
            "status": "rejected",
            "confidence": 0.2,
            "notes": "Text evidence did not support the claimed milestone",
        },
        {
            "record_id": "doc:002:p5:system_architecture_diagram",
            "fact_type": "architecture_component",
            "field": "system_architecture",
            "value": "AI analysis server",
            "evidence_quote": "AI 분석 서버",
            "reviewer": "reviewer_b",
            "status": "needs_review",
            "confidence": 0.5,
        },
    ]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def test_merge_visual_facts_adds_only_accepted_structured_facts() -> None:
    records, summary = merge_visual_facts(_records(), _facts())

    first = records[0]
    assert len(first["structured_facts"]) == 1
    assert first["structured_facts"][0] == {
        "fact_id": "doc:001:p3:gantt_schedule:fact:000",
        "fact_type": "visual_type_present",
        "field": "schedule",
        "value": "Gantt schedule is present on page 3",
        "evidence_quote": "manual page review",
        "reviewer": "reviewer_a",
        "confidence": 0.9,
        "source_status": "accepted",
        "notes": "",
    }
    assert records[1]["structured_facts"] == []
    assert summary["record_count"] == 2
    assert summary["reviewed_needs_extraction_count"] == 1
    assert summary["accepted_record_count"] == 1
    assert summary["accepted_record_ratio"] == 1.0
    assert summary["fact_count"] == 3
    assert summary["accepted_fact_count"] == 1
    assert summary["rejected_fact_count"] == 1
    assert summary["needs_review_fact_count"] == 1
    assert summary["unsupported_claim_count"] == 1
    assert summary["unknown_record_count"] == 0


def test_merge_visual_facts_rejects_unknown_record_id() -> None:
    bad_fact = _facts()[0] | {"record_id": "doc:999:p1:gantt_schedule"}

    with pytest.raises(ValueError, match="unknown record_id"):
        merge_visual_facts(_records(), [bad_fact])


def test_merge_visual_facts_rejects_field_outside_record_business_fields() -> None:
    bad_fact = _facts()[0] | {"field": "budget"}

    with pytest.raises(ValueError, match="field .* is not listed"):
        merge_visual_facts(_records(), [bad_fact])


def test_merge_visual_facts_rejects_incompatible_fact_type() -> None:
    bad_fact = _facts()[0] | {"fact_type": "architecture_component"}

    with pytest.raises(ValueError, match="incompatible fact_type"):
        merge_visual_facts(_records(), [bad_fact])


def test_write_visual_fact_artifacts_writes_records_summary_and_report(
    tmp_path: Path,
) -> None:
    records, summary = merge_visual_facts(_records(), _facts())

    write_visual_fact_artifacts(records, summary, tmp_path / "reviewed")

    assert (tmp_path / "reviewed" / "records.jsonl").is_file()
    saved_summary = json.loads(
        (tmp_path / "reviewed" / "summary.json").read_text(encoding="utf-8")
    )
    assert saved_summary["accepted_fact_count"] == 1
    report = (tmp_path / "reviewed" / "review_report.md").read_text(encoding="utf-8")
    assert "Visual Fact Review Report" in report
    assert "accepted_fact_count" in report


def test_run_visual_fact_review_reads_records_and_fact_inputs(tmp_path: Path) -> None:
    records_path = tmp_path / "records.jsonl"
    facts_path = tmp_path / "facts.jsonl"
    out_dir = tmp_path / "reviewed"
    _write_jsonl(records_path, _records())
    _write_jsonl(facts_path, _facts())

    summary = run_visual_fact_review(
        records_path=records_path,
        facts_path=facts_path,
        out_dir=out_dir,
    )

    assert summary["accepted_fact_count"] == 1
    reviewed_record = json.loads(
        (out_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert reviewed_record["structured_facts"][0]["fact_type"] == "visual_type_present"


def test_run_visual_fact_review_cli_writes_outputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from rfp_rag.run_visual_fact_review import main

    records_path = tmp_path / "records.jsonl"
    facts_path = tmp_path / "facts.jsonl"
    out_dir = tmp_path / "reviewed"
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
            ]
        )
        == 0
    )

    stdout = capsys.readouterr().out
    payload = json.loads(stdout)
    assert payload["accepted_fact_count"] == 1
    assert (out_dir / "records.jsonl").is_file()
    assert (out_dir / "summary.json").is_file()
    assert (out_dir / "review_report.md").is_file()
