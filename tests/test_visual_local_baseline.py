from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.visual_local_baseline import (
    build_visual_local_candidates,
    run_visual_local_baseline,
)


def _records() -> list[dict]:
    return [
        {
            "record_id": "doc:001:p3:gantt_schedule",
            "doc_id": "doc:001",
            "page": 3,
            "visual_type": "gantt_schedule",
            "business_fields": ["schedule", "requirements"],
            "review_status": "reviewed_needs_extraction",
        },
        {
            "record_id": "doc:002:p5:system_architecture_diagram",
            "doc_id": "doc:002",
            "page": 5,
            "visual_type": "system_architecture_diagram",
            "business_fields": ["requirements", "system_architecture"],
            "review_status": "reviewed_needs_extraction",
        },
        {
            "record_id": "doc:003:p7:organization_chart",
            "doc_id": "doc:003",
            "page": 7,
            "visual_type": "organization_chart",
            "business_fields": ["schedule", "requirements"],
            "review_status": "reviewed_needs_extraction",
        },
        {
            "record_id": "doc:004:p1:dashboard_screenshot",
            "doc_id": "doc:004",
            "page": 1,
            "visual_type": "dashboard_screenshot",
            "business_fields": ["requirements"],
            "review_status": "needs_page_review",
        },
    ]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def test_build_visual_local_candidates_filters_and_selects_fields() -> None:
    candidates, summary = build_visual_local_candidates(_records())

    assert [candidate["record_id"] for candidate in candidates] == [
        "doc:001:p3:gantt_schedule",
        "doc:002:p5:system_architecture_diagram",
        "doc:003:p7:organization_chart",
    ]
    assert candidates[0]["fact_type"] == "visual_type_present"
    assert candidates[0]["field"] == "schedule"
    assert candidates[1]["field"] == "system_architecture"
    assert candidates[2]["field"] == "requirements"
    assert candidates[2]["fact_type"] == "visual_type_present"
    assert summary["extractor"] == "visual_local_record_baseline_v1"
    assert summary["source_record_count"] == 4
    assert summary["candidate_fact_count"] == 3
    assert summary["skipped_record_count"] == 1
    assert summary["field_counts"] == {
        "requirements": 1,
        "schedule": 1,
        "system_architecture": 1,
    }


def test_run_visual_local_baseline_writes_candidate_facts_and_summary(
    tmp_path: Path,
) -> None:
    records_path = tmp_path / "records.jsonl"
    out_dir = tmp_path / "baseline"
    _write_jsonl(records_path, _records())

    summary = run_visual_local_baseline(records_path, out_dir)

    assert summary["candidate_fact_count"] == 3
    candidate_rows = [
        json.loads(line)
        for line in (out_dir / "candidate_facts.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert candidate_rows[0]["extractor"] == "visual_local_record_baseline_v1"
    assert (out_dir / "summary.json").is_file()


def test_run_visual_local_baseline_cli_writes_outputs(tmp_path: Path, capsys) -> None:
    from rfp_rag.run_visual_local_baseline import main

    records_path = tmp_path / "records.jsonl"
    out_dir = tmp_path / "baseline"
    _write_jsonl(records_path, _records())

    assert main(["--records", str(records_path), "--out", str(out_dir)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["candidate_fact_count"] == 3
    assert (out_dir / "candidate_facts.jsonl").is_file()
