from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


DECISION = "visual_gold_review_batch"
DEFAULT_REVIEW_STATUS = "needs_page_review"
DEFAULT_REVIEWER = "manual_page_review_pending"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"jsonl file not found: {path}")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"jsonl row must be an object on {path}:{line_number}")
            rows.append(row)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _existing_fact_record_ids(facts: Iterable[dict[str, Any]]) -> set[str]:
    return {
        str(fact.get("record_id") or "").strip()
        for fact in facts
        if str(fact.get("record_id") or "").strip()
    }


def _template_field(record: dict[str, Any]) -> str:
    fields = [str(field).strip() for field in record.get("business_fields") or []]
    return next((field for field in fields if field), "requirements")


def _template_fact(record: dict[str, Any]) -> dict[str, Any]:
    visual_type = str(record.get("visual_type") or "visual_structure")
    return {
        "record_id": str(record["record_id"]),
        "fact_type": "visual_type_present",
        "field": _template_field(record),
        "value": f"{visual_type} page-level visual evidence requires reviewer decision",
        "evidence_quote": "",
        "reviewer": DEFAULT_REVIEWER,
        "status": "needs_review",
        "confidence": 0.0,
        "notes": (
            "Fill status as accepted or rejected after reviewing the referenced "
            "PDF page; accepted facts require evidence_quote."
        ),
    }


def build_visual_review_batch(
    records: Iterable[dict[str, Any]],
    facts: Iterable[dict[str, Any]],
    *,
    review_status: str = DEFAULT_REVIEW_STATUS,
    max_records: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rows = list(records)
    fact_rows = list(facts)
    existing_record_ids = _existing_fact_record_ids(fact_rows)
    selected_records = [
        record
        for record in rows
        if record.get("review_status") == review_status
        and str(record.get("record_id") or "") not in existing_record_ids
    ]
    if max_records is not None:
        selected_records = selected_records[:max_records]

    facts_template = [_template_fact(record) for record in selected_records]
    visual_type_counts = Counter(
        str(record.get("visual_type") or "visual_structure")
        for record in selected_records
    )
    business_field_counts: Counter[str] = Counter()
    for record in selected_records:
        for field in record.get("business_fields") or []:
            business_field_counts[str(field)] += 1

    summary = {
        "decision": DECISION,
        "review_status_filter": review_status,
        "source_record_count": len(rows),
        "existing_fact_count": len(fact_rows),
        "existing_fact_record_count": len(existing_record_ids),
        "eligible_record_count": sum(
            1 for record in rows if record.get("review_status") == review_status
        ),
        "selected_record_count": len(selected_records),
        "max_records": max_records,
        "selected_visual_type_counts": dict(sorted(visual_type_counts.items())),
        "selected_business_field_counts": dict(sorted(business_field_counts.items())),
        "next_step": (
            "review each PDF page, then edit facts_template.jsonl statuses to "
            "accepted or rejected before merging with run_visual_fact_review"
        ),
    }
    return selected_records, facts_template, summary


def _render_review_queue(
    records: list[dict[str, Any]],
    facts_template: list[dict[str, Any]],
    summary: dict[str, Any],
) -> str:
    facts_by_record = {fact["record_id"]: fact for fact in facts_template}
    lines = [
        "# Visual Gold Review Batch",
        "",
        "## Summary",
        "",
    ]
    for key in [
        "decision",
        "review_status_filter",
        "source_record_count",
        "existing_fact_record_count",
        "eligible_record_count",
        "selected_record_count",
        "selected_visual_type_counts",
        "next_step",
    ]:
        lines.append(f"- {key}: {summary.get(key)}")
    lines.extend(["", "## Records", ""])
    for record in records:
        evidence = record.get("evidence_ref") or {}
        fact = facts_by_record[str(record["record_id"])]
        lines.extend(
            [
                f"### {record['record_id']}",
                "",
                f"- doc_id: {record.get('doc_id')}",
                f"- page: {record.get('page')}",
                f"- visual_type: {record.get('visual_type')}",
                f"- business_fields: {', '.join(record.get('business_fields') or [])}",
                f"- pdf_path: {evidence.get('pdf_path')}",
                f"- source_visual_elements: {record.get('source_visual_elements')}",
                "",
                "Suggested fact template:",
                "",
                "```json",
                json.dumps(fact, ensure_ascii=False, sort_keys=True),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def write_visual_review_batch_artifacts(
    records: list[dict[str, Any]],
    facts_template: list[dict[str, Any]],
    summary: dict[str, Any],
    out_dir: Path | str,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out / "records.jsonl", records)
    _write_jsonl(out / "facts_template.jsonl", facts_template)
    _write_json(out / "summary.json", summary)
    (out / "review_queue.md").write_text(
        _render_review_queue(records, facts_template, summary),
        encoding="utf-8",
    )
    return summary


def run_visual_review_batch(
    records_path: Path | str,
    facts_path: Path | str,
    out_dir: Path | str,
    *,
    review_status: str = DEFAULT_REVIEW_STATUS,
    max_records: int | None = None,
) -> dict[str, Any]:
    records = _read_jsonl(Path(records_path))
    facts = _read_jsonl(Path(facts_path))
    batch_records, facts_template, summary = build_visual_review_batch(
        records,
        facts,
        review_status=review_status,
        max_records=max_records,
    )
    return write_visual_review_batch_artifacts(
        batch_records,
        facts_template,
        summary,
        out_dir,
    )
