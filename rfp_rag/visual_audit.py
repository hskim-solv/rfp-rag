from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


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


def _manifest_by_doc(parsed_dir: Path) -> dict[str, dict[str, Any]]:
    return {row["doc_id"]: row for row in _read_jsonl(parsed_dir / "manifest.jsonl")}


def _selected_pages(row: dict[str, Any], max_pages_per_doc: int) -> list[int]:
    pages: list[int] = []
    for value in list(row.get("chart_candidate_pages") or []) + list(
        row.get("visual_signal_pages") or []
    ):
        page = int(value)
        if page not in pages:
            pages.append(page)
        if len(pages) >= max_pages_per_doc:
            break
    return pages


def _float_or_default(value: Any, default: float) -> float:
    if value is None:
        return default
    return float(value)


def _audit_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    flags = set(row.get("risk_flags") or [])
    if row.get("chart_candidate_pages"):
        reasons.append("chart_or_drawing_signal_present")
    if row.get("pdf_image_count"):
        reasons.append("image_signal_present")
    if (
        "table_signal_loss" in flags
        or _float_or_default(row.get("table_like_recall"), 1.0) < 0.8
    ):
        reasons.append("table_signal_loss")
    if _float_or_default(row.get("quality_score"), 1.0) < 0.9:
        reasons.append("lower_parser_quality")
    if not reasons and "visual_content_present" in flags:
        reasons.append("visual_content_present")
    return reasons


def _priority_score(row: dict[str, Any]) -> float:
    quality = _float_or_default(row.get("quality_score"), 1.0)
    table_recall = _float_or_default(row.get("table_like_recall"), 1.0)
    chart_pages = len(row.get("chart_candidate_pages") or [])
    visual_pages = len(row.get("visual_signal_pages") or [])
    images = int(row.get("pdf_image_count") or 0)
    drawings = int(row.get("pdf_drawing_count") or 0)
    flags = set(row.get("risk_flags") or [])
    score = (
        chart_pages * 5.0
        + min(visual_pages, 10) * 0.5
        + min(images, 50) * 0.2
        + min(drawings, 500) * 0.02
        + max(0.0, 1.0 - quality) * 10.0
        + max(0.0, 1.0 - table_recall) * 5.0
    )
    if "table_signal_loss" in flags:
        score += 3.0
    if "chart_or_drawing_signal_present" in flags:
        score += 2.0
    return round(score, 4)


def _review_questions(selected_pages: list[int]) -> list[str]:
    page_label = ", ".join(str(page) for page in selected_pages) or "(no page selected)"
    return [
        f"선택 페이지({page_label})의 시각 요소가 입찰 검토 정보인가?",
        "동일 정보가 추출 텍스트/표에도 존재하는가, 아니면 visual-only 정보인가?",
        "예산, 일정, 평가 기준, 참가 자격, 요구사항, 시스템 구성 중 어떤 업무 항목에 영향을 주는가?",
        "OCR/VLM 파싱이 필요하면 어떤 필드명과 근거 페이지로 구조화해야 하는가?",
    ]


def select_visual_audit_samples(
    parsed_dir: Path | str,
    quality_records: Iterable[dict[str, Any]],
    *,
    max_docs: int = 15,
    max_pages_per_doc: int = 5,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parsed_path = Path(parsed_dir)
    manifest = _manifest_by_doc(parsed_path)
    candidates: list[dict[str, Any]] = []
    for row in quality_records:
        reasons = _audit_reasons(row)
        if not reasons:
            continue
        doc_id = str(row.get("doc_id") or "")
        parsed_record = manifest.get(doc_id, {})
        selected_pages = _selected_pages(row, max_pages_per_doc)
        candidates.append(
            {
                "doc_id": doc_id,
                "source_filename": parsed_record.get("csv_filename_raw")
                or parsed_record.get("source_filename")
                or Path(str(parsed_record.get("source_path") or "")).name
                or None,
                "parser_backend": parsed_record.get("parser_backend")
                or row.get("parser_backend"),
                "pdf_path": parsed_record.get("converted_pdf_path"),
                "page_text_path": parsed_record.get("page_text_path"),
                "quality_score": row.get("quality_score"),
                "table_like_recall": row.get("table_like_recall"),
                "pdf_image_count": row.get("pdf_image_count", 0),
                "pdf_drawing_count": row.get("pdf_drawing_count", 0),
                "visual_signal_pages": list(row.get("visual_signal_pages") or []),
                "chart_candidate_pages": list(row.get("chart_candidate_pages") or []),
                "selected_pages": selected_pages,
                "risk_flags": list(row.get("risk_flags") or []),
                "audit_reasons": reasons,
                "audit_priority_score": _priority_score(row),
                "visual_parse_decision": "manual_audit_required",
                "review_questions": _review_questions(selected_pages),
            }
        )
    candidates.sort(
        key=lambda item: (
            -float(item.get("audit_priority_score") or 0.0),
            item.get("doc_id") or "",
        )
    )
    samples: list[dict[str, Any]] = []
    for rank, sample in enumerate(candidates[:max_docs], start=1):
        samples.append({"rank": rank, **sample})
    summary = {
        "candidate_count": len(candidates),
        "sample_count": len(samples),
        "max_docs": max_docs,
        "max_pages_per_doc": max_pages_per_doc,
        "visual_only_answer_risk": "unknown_until_manual_audit",
        "decision": "manual_visual_audit_before_ocr_vlm",
        "next_step": "review selected PDF pages and label visual-only business information",
    }
    return samples, summary


def _render_review_markdown(
    samples: list[dict[str, Any]], summary: dict[str, Any]
) -> str:
    lines = [
        "# Visual Parsing Audit",
        "",
        "## Summary",
        "",
        f"- candidate_count: {summary.get('candidate_count')}",
        f"- sample_count: {summary.get('sample_count')}",
        f"- decision: {summary.get('decision')}",
        f"- visual_only_answer_risk: {summary.get('visual_only_answer_risk')}",
        "",
        "## Samples",
        "",
    ]
    for sample in samples:
        lines.extend(
            [
                f"### {sample['rank']}. {sample['doc_id']}",
                "",
                f"- source_filename: {sample.get('source_filename')}",
                f"- pdf_path: {sample.get('pdf_path')}",
                f"- page_text_path: {sample.get('page_text_path')}",
                f"- selected_pages: {sample.get('selected_pages')}",
                f"- audit_priority_score: {sample.get('audit_priority_score')}",
                f"- audit_reasons: {', '.join(sample.get('audit_reasons') or [])}",
                "- review_questions:",
            ]
        )
        for question in sample.get("review_questions") or []:
            lines.append(f"  - {question}")
        lines.append("")
    return "\n".join(lines)


def write_visual_audit_artifacts(
    samples: list[dict[str, Any]],
    summary: dict[str, Any],
    out_dir: Path | str,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out / "samples.jsonl", samples)
    _write_json(out / "summary.json", summary)
    (out / "review.md").write_text(
        _render_review_markdown(samples, summary), encoding="utf-8"
    )
    return summary


def run_visual_audit(
    parsed_dir: Path | str,
    quality_dir: Path | str,
    out_dir: Path | str,
    *,
    max_docs: int = 15,
    max_pages_per_doc: int = 5,
) -> dict[str, Any]:
    quality_records = _read_jsonl(Path(quality_dir) / "per_doc.jsonl")
    samples, summary = select_visual_audit_samples(
        parsed_dir,
        quality_records,
        max_docs=max_docs,
        max_pages_per_doc=max_pages_per_doc,
    )
    return write_visual_audit_artifacts(samples, summary, out_dir)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select visual/chart-heavy RFP pages for manual parsing impact audit."
    )
    parser.add_argument("--parsed-dir", required=True, type=Path)
    parser.add_argument("--quality-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--max-docs", default=15, type=int)
    parser.add_argument("--max-pages-per-doc", default=5, type=int)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    summary = run_visual_audit(
        args.parsed_dir,
        args.quality_dir,
        args.out,
        max_docs=args.max_docs,
        max_pages_per_doc=args.max_pages_per_doc,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
