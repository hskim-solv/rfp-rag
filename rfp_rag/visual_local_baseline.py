from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

EXTRACTOR_NAME = "visual_local_record_baseline_v1"
REVIEW_STATUS_FILTER = "reviewed_needs_extraction"

FIELD_PRIORITY_BY_VISUAL_TYPE = {
    "gantt_schedule": ("schedule", "requirements", "system_architecture"),
    "system_architecture_diagram": ("system_architecture", "requirements", "schedule"),
    "organization_chart": ("requirements", "schedule", "system_architecture"),
    "requirements_table": ("requirements", "schedule", "system_architecture"),
    "dashboard_screenshot": ("requirements",),
}


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


def _choose_field(record: dict[str, Any]) -> str:
    fields = [str(field) for field in record.get("business_fields") or []]
    visual_type = str(record.get("visual_type") or "visual_structure")
    for field in FIELD_PRIORITY_BY_VISUAL_TYPE.get(visual_type, ()):
        if field in fields:
            return field
    return fields[0] if fields else "requirements"


def _candidate_fact(record: dict[str, Any]) -> dict[str, Any]:
    visual_type = str(record.get("visual_type") or "visual_structure")
    field = _choose_field(record)
    return {
        "record_id": str(record["record_id"]),
        "fact_type": "visual_type_present",
        "field": field,
        "value": f"{visual_type} candidate detected from visual-structure record",
        "extractor": EXTRACTOR_NAME,
        "confidence": float(record.get("confidence") or 0.5),
    }


def build_visual_local_candidates(
    records: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = list(records)
    candidates = [
        _candidate_fact(record)
        for record in rows
        if record.get("review_status") == REVIEW_STATUS_FILTER
    ]
    field_counts = Counter(candidate["field"] for candidate in candidates)
    visual_type_counts = Counter(
        str(record.get("visual_type") or "visual_structure")
        for record in rows
        if record.get("review_status") == REVIEW_STATUS_FILTER
    )
    summary = {
        "decision": "visual_local_record_baseline",
        "extractor": EXTRACTOR_NAME,
        "review_status_filter": REVIEW_STATUS_FILTER,
        "source_record_count": len(rows),
        "candidate_fact_count": len(candidates),
        "skipped_record_count": len(rows) - len(candidates),
        "field_counts": dict(sorted(field_counts.items())),
        "visual_type_counts": dict(sorted(visual_type_counts.items())),
    }
    return candidates, summary


def run_visual_local_baseline(
    records_path: Path | str,
    out_dir: Path | str,
) -> dict[str, Any]:
    records = _read_jsonl(Path(records_path))
    candidates, summary = build_visual_local_candidates(records)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out / "candidate_facts.jsonl", candidates)
    _write_json(out / "summary.json", summary)
    return summary
