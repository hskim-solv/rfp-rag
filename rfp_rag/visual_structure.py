from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


EXTRACTOR_NAME = "manual_review_seed_v1"

FIELD_ALIASES = {
    "schedule": "schedule",
    "requirements": "requirements",
    "system architecture": "system_architecture",
    "system_architecture": "system_architecture",
    "budget": "budget",
    "evaluation": "evaluation",
    "qualification": "qualification",
}

VISUAL_TYPE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("gantt_schedule", ("gantt", "schedule", "일정")),
    ("organization_chart", ("organization chart", "조직도")),
    (
        "system_architecture_diagram",
        (
            "architecture",
            "target service model",
            "system diagram",
            "시스템 구성",
            "목표 서비스",
        ),
    ),
    ("dashboard_screenshot", ("dashboard", "screenshot", "ui ")),
    ("requirements_table", ("requirements", "summary/list", "요구사항")),
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"jsonl file not found: {path}")
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _clean_markdown_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("`", "").strip())


def _split_markdown_row(line: str) -> list[str]:
    return [_clean_markdown_cell(cell) for cell in line.strip().strip("|").split("|")]


def _normalize_fields(value: str) -> list[str]:
    cleaned = value.strip().lower()
    if not cleaned or cleaned == "none":
        return []
    fields: list[str] = []
    for part in cleaned.split(","):
        key = _clean_markdown_cell(part).lower()
        field = FIELD_ALIASES.get(key)
        if field and field not in fields:
            fields.append(field)
    return fields


def _infer_visual_types(visual_elements: str) -> list[str]:
    haystack = visual_elements.lower()
    visual_types: list[str] = []
    for visual_type, keywords in VISUAL_TYPE_RULES:
        if any(keyword in haystack for keyword in keywords):
            visual_types.append(visual_type)
    return visual_types or ["visual_structure"]


def _confidence(visual_only_risk: str, recommendation: str) -> float:
    risk = visual_only_risk.lower()
    rec = recommendation.lower()
    if risk == "yes" and rec == "adopt now":
        return 0.7
    if risk == "yes":
        return 0.6
    if risk == "uncertain":
        return 0.5
    return 0.0


def _review_status(visual_only_risk: str, recommendation: str) -> str:
    if recommendation.lower() == "inspect individual page":
        return "needs_page_review"
    if visual_only_risk.lower() == "yes":
        return "reviewed_needs_extraction"
    if visual_only_risk.lower() == "uncertain":
        return "needs_page_review"
    return "deferred_no_visual_record"


def parse_manual_review_markdown(path: Path | str) -> list[dict[str, Any]]:
    review_path = Path(path)
    rows: list[dict[str, Any]] = []
    for line in review_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = _split_markdown_row(line)
        if len(cells) != 6:
            continue
        if cells[0].lower() in {"rank", "---:"} or set(cells[0]) <= {"-", ":"}:
            continue
        rank, doc_id, visual_elements, risk, fields, recommendation = cells
        if not doc_id.startswith("doc:"):
            continue
        rows.append(
            {
                "rank": int(rank),
                "doc_id": doc_id,
                "visual_elements": visual_elements,
                "visual_only_risk": risk.lower(),
                "business_fields": _normalize_fields(fields),
                "recommendation": recommendation.lower(),
                "visual_types": _infer_visual_types(visual_elements),
            }
        )
    return rows


def _sample_by_doc(samples: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(sample.get("doc_id")): sample for sample in samples}


def build_visual_structure_records(
    samples: Iterable[dict[str, Any]],
    review_findings: Iterable[dict[str, Any]],
    *,
    review_path: Path | str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    samples_by_doc = _sample_by_doc(samples)
    findings = list(review_findings)
    records: list[dict[str, Any]] = []
    skipped_no_risk_count = 0
    missing_sample_count = 0

    for finding in findings:
        status = _review_status(
            str(finding.get("visual_only_risk") or ""),
            str(finding.get("recommendation") or ""),
        )
        if status == "deferred_no_visual_record":
            skipped_no_risk_count += 1
            continue
        doc_id = str(finding["doc_id"])
        sample = samples_by_doc.get(doc_id)
        if sample is None:
            missing_sample_count += 1
            continue
        pages = [int(page) for page in sample.get("selected_pages") or []]
        for page in pages:
            for visual_type in finding.get("visual_types") or ["visual_structure"]:
                records.append(
                    {
                        "record_id": f"{doc_id}:p{page}:{visual_type}",
                        "doc_id": doc_id,
                        "page": page,
                        "visual_type": visual_type,
                        "business_fields": list(finding.get("business_fields") or []),
                        "structured_facts": [],
                        "evidence_ref": {
                            "pdf_path": sample.get("pdf_path"),
                            "page_text_path": sample.get("page_text_path"),
                            "source_filename": sample.get("source_filename"),
                            "manual_review_path": str(review_path),
                        },
                        "extractor": EXTRACTOR_NAME,
                        "confidence": _confidence(
                            str(finding.get("visual_only_risk") or ""),
                            str(finding.get("recommendation") or ""),
                        ),
                        "review_status": status,
                        "source_visual_elements": finding.get("visual_elements"),
                        "source_recommendation": finding.get("recommendation"),
                    }
                )

    visual_type_counts: Counter[str] = Counter()
    business_field_counts: Counter[str] = Counter()
    review_status_counts: Counter[str] = Counter()
    for record in records:
        visual_type_counts[str(record["visual_type"])] += 1
        review_status_counts[str(record["review_status"])] += 1
        for field in record.get("business_fields") or []:
            business_field_counts[str(field)] += 1

    summary = {
        "decision": "targeted_visual_structure_extraction_seed",
        "extractor": EXTRACTOR_NAME,
        "input_sample_count": len(samples_by_doc),
        "review_finding_count": len(findings),
        "record_count": len(records),
        "skipped_no_risk_count": skipped_no_risk_count,
        "missing_sample_count": missing_sample_count,
        "visual_type_counts": dict(sorted(visual_type_counts.items())),
        "business_field_counts": dict(sorted(business_field_counts.items())),
        "review_status_counts": dict(sorted(review_status_counts.items())),
        "review_path": str(review_path),
        "next_step": "fill structured_facts with targeted page-level extraction and reviewer validation",
    }
    return records, summary


def _render_review_queue(records: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# Visual Structure Review Queue",
        "",
        "## Summary",
        "",
        f"- decision: {summary.get('decision')}",
        f"- extractor: {summary.get('extractor')}",
        f"- record_count: {summary.get('record_count')}",
        "",
        "## Records",
        "",
    ]
    for record in records:
        evidence = record.get("evidence_ref") or {}
        lines.extend(
            [
                f"### {record['record_id']}",
                "",
                f"- doc_id: {record.get('doc_id')}",
                f"- page: {record.get('page')}",
                f"- visual_type: {record.get('visual_type')}",
                f"- business_fields: {', '.join(record.get('business_fields') or [])}",
                f"- review_status: {record.get('review_status')}",
                f"- confidence: {record.get('confidence')}",
                f"- pdf_path: {evidence.get('pdf_path')}",
                f"- source_visual_elements: {record.get('source_visual_elements')}",
                "",
            ]
        )
    return "\n".join(lines)


def write_visual_structure_artifacts(
    records: list[dict[str, Any]],
    summary: dict[str, Any],
    out_dir: Path | str,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out / "records.jsonl", records)
    _write_json(out / "summary.json", summary)
    (out / "review_queue.md").write_text(
        _render_review_queue(records, summary), encoding="utf-8"
    )
    return summary


def run_visual_structure_extraction(
    audit_dir: Path | str,
    review_path: Path | str,
    out_dir: Path | str,
) -> dict[str, Any]:
    samples = _read_jsonl(Path(audit_dir) / "samples.jsonl")
    findings = parse_manual_review_markdown(review_path)
    records, summary = build_visual_structure_records(
        samples,
        findings,
        review_path=review_path,
    )
    return write_visual_structure_artifacts(records, summary, out_dir)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create targeted visual-structure seed records from visual audit review evidence."
    )
    parser.add_argument("--audit-dir", required=True, type=Path)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    summary = run_visual_structure_extraction(args.audit_dir, args.review, args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
