from __future__ import annotations

import json
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

VALID_STATUSES = {"accepted", "rejected", "needs_review"}

VISUAL_GOLD_DEFAULT_THRESHOLDS = {
    "min_resolved_record_ratio": 0.80,
    "min_accepted_fact_count": 1,
    "max_needs_review_fact_count": 0,
    "max_unknown_record_count": 0,
}

FACT_TYPE_FIELDS = {
    "visual_type_present": {
        "schedule",
        "requirements",
        "system_architecture",
        "budget",
        "evaluation",
        "qualification",
    },
    "business_field_affected": {
        "schedule",
        "requirements",
        "system_architecture",
        "budget",
        "evaluation",
        "qualification",
    },
    "schedule_milestone": {"schedule"},
    "schedule_duration": {"schedule"},
    "schedule_dependency": {"schedule"},
    "requirement_item": {"requirements"},
    "architecture_component": {"system_architecture"},
    "architecture_integration": {"system_architecture"},
    "ui_requirement": {"requirements"},
}

VISUAL_TYPE_FACT_TYPES = {
    "gantt_schedule": {
        "visual_type_present",
        "business_field_affected",
        "schedule_milestone",
        "schedule_duration",
        "schedule_dependency",
        "requirement_item",
    },
    "organization_chart": {
        "visual_type_present",
        "business_field_affected",
        "requirement_item",
    },
    "requirements_table": {
        "visual_type_present",
        "business_field_affected",
        "requirement_item",
    },
    "system_architecture_diagram": {
        "visual_type_present",
        "business_field_affected",
        "architecture_component",
        "architecture_integration",
        "requirement_item",
    },
    "dashboard_screenshot": {
        "visual_type_present",
        "business_field_affected",
        "ui_requirement",
        "requirement_item",
    },
    "visual_structure": {
        "visual_type_present",
        "business_field_affected",
    },
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"jsonl file not found: {path}")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on {path}:{line_number}") from exc
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


def _require_non_empty(fact: dict[str, Any], key: str) -> str:
    value = str(fact.get(key) or "").strip()
    if not value:
        raise ValueError(f"fact for record_id {fact.get('record_id')!r} missing {key}")
    return value


def _validate_fact(record: dict[str, Any], fact: dict[str, Any]) -> None:
    status = _require_non_empty(fact, "status")
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status {status!r}")

    fact_type = _require_non_empty(fact, "fact_type")
    field = _require_non_empty(fact, "field")
    _require_non_empty(fact, "value")
    _require_non_empty(fact, "reviewer")
    if status == "accepted":
        _require_non_empty(fact, "evidence_quote")

    business_fields = set(record.get("business_fields") or [])
    if field not in business_fields:
        raise ValueError(
            f"field {field!r} is not listed in business_fields for {record['record_id']}"
        )
    allowed_fields = FACT_TYPE_FIELDS.get(fact_type)
    if allowed_fields is None or field not in allowed_fields:
        raise ValueError(f"incompatible fact_type {fact_type!r} for field {field!r}")
    visual_type = str(record.get("visual_type") or "visual_structure")
    allowed_types = VISUAL_TYPE_FACT_TYPES.get(visual_type, {"visual_type_present"})
    if fact_type not in allowed_types:
        raise ValueError(
            f"incompatible fact_type {fact_type!r} for visual_type {visual_type!r}"
        )


def _accepted_fact(record_id: str, index: int, fact: dict[str, Any]) -> dict[str, Any]:
    confidence = fact.get("confidence")
    return {
        "fact_id": f"{record_id}:fact:{index:03d}",
        "fact_type": str(fact["fact_type"]).strip(),
        "field": str(fact["field"]).strip(),
        "value": str(fact["value"]).strip(),
        "evidence_quote": str(fact.get("evidence_quote") or "").strip(),
        "reviewer": str(fact["reviewer"]).strip(),
        "confidence": float(confidence) if confidence is not None else None,
        "source_status": "accepted",
        "notes": str(fact.get("notes") or "").strip(),
    }


def merge_visual_facts(
    records: Iterable[dict[str, Any]],
    facts: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    merged_records = [deepcopy(record) for record in records]
    by_record = {str(record["record_id"]): record for record in merged_records}
    accepted_by_record: dict[str, list[dict[str, Any]]] = defaultdict(list)
    status_counts: Counter[str] = Counter()
    status_records: dict[str, set[str]] = defaultdict(set)
    facts_materialized = list(facts)

    for fact in facts_materialized:
        record_id = _require_non_empty(fact, "record_id")
        record = by_record.get(record_id)
        if record is None:
            raise ValueError(f"unknown record_id {record_id!r}")
        _validate_fact(record, fact)
        status = str(fact["status"]).strip()
        status_counts[status] += 1
        status_records[status].add(record_id)
        if status == "accepted":
            accepted_by_record[record_id].append(
                _accepted_fact(record_id, len(accepted_by_record[record_id]), fact)
            )

    for record in merged_records:
        record["structured_facts"] = accepted_by_record.get(
            str(record["record_id"]),
            [],
        )

    reviewed_needs_extraction_count = sum(
        1
        for record in merged_records
        if record.get("review_status") == "reviewed_needs_extraction"
    )
    accepted_record_count = sum(
        1 for record in merged_records if record.get("structured_facts")
    )
    resolved_record_ids = status_records["accepted"] | status_records["rejected"]
    denominator = reviewed_needs_extraction_count or len(merged_records) or 1
    summary = {
        "decision": "reviewer_visual_fact_gold_set",
        "record_count": len(merged_records),
        "reviewed_needs_extraction_count": reviewed_needs_extraction_count,
        "accepted_record_count": accepted_record_count,
        "accepted_record_ratio": round(accepted_record_count / denominator, 8),
        "rejected_record_count": len(status_records["rejected"]),
        "needs_review_record_count": len(status_records["needs_review"]),
        "resolved_record_count": len(resolved_record_ids),
        "resolved_record_ratio": round(len(resolved_record_ids) / denominator, 8),
        "fact_count": len(facts_materialized),
        "accepted_fact_count": status_counts["accepted"],
        "rejected_fact_count": status_counts["rejected"],
        "needs_review_fact_count": status_counts["needs_review"],
        "unsupported_claim_count": status_counts["rejected"],
        "unknown_record_count": 0,
    }
    return merged_records, summary


def _render_review_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Visual Fact Review Report",
        "",
        "## Summary",
        "",
    ]
    for key in [
        "decision",
        "record_count",
        "reviewed_needs_extraction_count",
        "accepted_record_count",
        "accepted_record_ratio",
        "rejected_record_count",
        "needs_review_record_count",
        "resolved_record_count",
        "resolved_record_ratio",
        "fact_count",
        "accepted_fact_count",
        "rejected_fact_count",
        "needs_review_fact_count",
        "unsupported_claim_count",
        "unknown_record_count",
    ]:
        lines.append(f"- {key}: {summary.get(key)}")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Accepted facts are reviewer gold labels for later OCR/VLM comparison.",
            "Rejected facts are negative reviewer gold labels and are not merged.",
            "Needs-review facts are retained in summary counts but are not merged.",
            "",
        ]
    )
    return "\n".join(lines)


def write_visual_fact_artifacts(
    records: list[dict[str, Any]],
    summary: dict[str, Any],
    out_dir: Path | str,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out / "records.jsonl", records)
    _write_json(out / "summary.json", summary)
    (out / "review_report.md").write_text(
        _render_review_report(summary), encoding="utf-8"
    )
    return summary


def check_visual_gold_summary(
    summary: dict[str, Any],
    *,
    min_resolved_record_ratio: float = VISUAL_GOLD_DEFAULT_THRESHOLDS[
        "min_resolved_record_ratio"
    ],
    min_accepted_fact_count: int = VISUAL_GOLD_DEFAULT_THRESHOLDS[
        "min_accepted_fact_count"
    ],
    max_needs_review_fact_count: int = VISUAL_GOLD_DEFAULT_THRESHOLDS[
        "max_needs_review_fact_count"
    ],
    max_unknown_record_count: int = VISUAL_GOLD_DEFAULT_THRESHOLDS[
        "max_unknown_record_count"
    ],
) -> dict[str, Any]:
    thresholds = {
        "min_resolved_record_ratio": min_resolved_record_ratio,
        "min_accepted_fact_count": min_accepted_fact_count,
        "max_needs_review_fact_count": max_needs_review_fact_count,
        "max_unknown_record_count": max_unknown_record_count,
    }
    checks = [
        (
            "resolved_record_ratio",
            float(summary.get("resolved_record_ratio") or 0.0),
            min_resolved_record_ratio,
            ">=",
        ),
        (
            "accepted_fact_count",
            int(summary.get("accepted_fact_count") or 0),
            min_accepted_fact_count,
            ">=",
        ),
        (
            "needs_review_fact_count",
            int(summary.get("needs_review_fact_count") or 0),
            max_needs_review_fact_count,
            "<=",
        ),
        (
            "unknown_record_count",
            int(summary.get("unknown_record_count") or 0),
            max_unknown_record_count,
            "<=",
        ),
    ]
    failures = []
    for metric, actual, threshold, comparator in checks:
        passed = actual >= threshold if comparator == ">=" else actual <= threshold
        if not passed:
            failures.append(
                {
                    "metric": metric,
                    "actual": actual,
                    "threshold": threshold,
                    "comparator": comparator,
                }
            )
    return {
        "decision": "visual_gold_gate",
        "ok": not failures,
        "thresholds": thresholds,
        "metrics": {
            "resolved_record_ratio": float(summary.get("resolved_record_ratio") or 0.0),
            "resolved_record_count": int(summary.get("resolved_record_count") or 0),
            "accepted_record_ratio": float(summary.get("accepted_record_ratio") or 0.0),
            "accepted_record_count": int(summary.get("accepted_record_count") or 0),
            "rejected_record_count": int(summary.get("rejected_record_count") or 0),
            "accepted_fact_count": int(summary.get("accepted_fact_count") or 0),
            "rejected_fact_count": int(summary.get("rejected_fact_count") or 0),
            "needs_review_fact_count": int(summary.get("needs_review_fact_count") or 0),
            "needs_review_record_count": int(
                summary.get("needs_review_record_count") or 0
            ),
            "unknown_record_count": int(summary.get("unknown_record_count") or 0),
            "unsupported_claim_count": int(summary.get("unsupported_claim_count") or 0),
        },
        "failures": failures,
    }


def run_visual_fact_review(
    records_path: Path | str,
    facts_path: Path | str,
    out_dir: Path | str,
) -> dict[str, Any]:
    records = _read_jsonl(Path(records_path))
    facts = _read_jsonl(Path(facts_path))
    merged_records, summary = merge_visual_facts(records, facts)
    return write_visual_fact_artifacts(merged_records, summary, out_dir)
