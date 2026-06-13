from __future__ import annotations

import importlib
import json
import re
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Iterable

RFP_KEY_TERMS = [
    "사업",
    "예산",
    "기간",
    "제출",
    "평가",
    "요구사항",
    "자격",
    "산출물",
    "계약",
    "보안",
]

TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
REQUIREMENT_ID_RE = re.compile(r"\b[A-Z]{2,4}[-_ ]?\d{2,4}\b")

PdfVisualAnalyzer = Callable[[Path], dict[str, Any]]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_text_path(value: Any) -> str:
    if not value:
        return ""
    path = Path(str(value))
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace").strip()


def _read_page_text_path(value: Any) -> tuple[str, int]:
    if not value:
        return "", 0
    path = Path(str(value))
    if not path.is_file():
        return "", 0
    rows = _read_jsonl(path)
    texts = [str(row.get("text") or "").strip() for row in rows if str(row.get("text") or "").strip()]
    return "\n".join(texts), len(texts)


def _tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in TOKEN_RE.finditer(text)}


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _token_overlap(parsed_text: str, page_text: str) -> dict[str, float]:
    parsed_tokens = _tokens(parsed_text)
    page_tokens = _tokens(page_text)
    if not parsed_tokens or not page_tokens:
        return {
            "text_pdf_token_recall": 0.0,
            "text_pdf_token_precision": 0.0,
            "text_pdf_token_f1": 0.0,
        }
    overlap = len(parsed_tokens & page_tokens)
    recall = overlap / len(page_tokens)
    precision = overlap / len(parsed_tokens)
    f1 = 0.0 if recall + precision == 0 else 2 * recall * precision / (recall + precision)
    return {
        "text_pdf_token_recall": _round(recall) or 0.0,
        "text_pdf_token_precision": _round(precision) or 0.0,
        "text_pdf_token_f1": _round(f1) or 0.0,
    }


def _key_term_recall(parsed_text: str, page_text: str) -> float:
    page_terms = [term for term in RFP_KEY_TERMS if term in page_text]
    if not page_terms:
        return 1.0
    parsed_hits = sum(1 for term in page_terms if term in parsed_text)
    return round(parsed_hits / len(page_terms), 4)


def _is_table_like_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    separator_count = stripped.count("|") + stripped.count("\t")
    if separator_count >= 2:
        return True
    if REQUIREMENT_ID_RE.search(stripped):
        return True
    return len(re.findall(r"\s{2,}", stripped)) >= 2


def _table_like_line_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if _is_table_like_line(line))


def _pdf_visual_signals(pdf_path: Path) -> dict[str, Any]:
    pymupdf = importlib.import_module("pymupdf")
    image_count = 0
    drawing_count = 0
    visual_signal_pages: list[int] = []
    chart_candidate_pages: list[int] = []
    with pymupdf.open(str(pdf_path)) as document:
        for index, page in enumerate(document, start=1):
            page_images = len(page.get_images(full=True))
            page_drawings = len(page.get_drawings())
            image_count += page_images
            drawing_count += page_drawings
            if page_images or page_drawings:
                visual_signal_pages.append(index)
            if page_drawings >= 12:
                chart_candidate_pages.append(index)
    return {
        "pdf_image_count": image_count,
        "pdf_drawing_count": drawing_count,
        "visual_signal_pages": visual_signal_pages,
        "chart_candidate_pages": chart_candidate_pages,
    }


def _safe_pdf_visual_signals(
    pdf_path: str | None,
    analyzer: PdfVisualAnalyzer,
) -> dict[str, Any]:
    if not pdf_path:
        return {
            "pdf_image_count": 0,
            "pdf_drawing_count": 0,
            "visual_signal_pages": [],
            "chart_candidate_pages": [],
            "visual_signal_error_reason": None,
        }
    path = Path(pdf_path)
    if not path.is_file():
        return {
            "pdf_image_count": 0,
            "pdf_drawing_count": 0,
            "visual_signal_pages": [],
            "chart_candidate_pages": [],
            "visual_signal_error_reason": "converted pdf not found",
        }
    try:
        signals = analyzer(path)
    except ImportError:
        return {
            "pdf_image_count": 0,
            "pdf_drawing_count": 0,
            "visual_signal_pages": [],
            "chart_candidate_pages": [],
            "visual_signal_error_reason": "pymupdf not installed",
        }
    except Exception as exc:
        return {
            "pdf_image_count": 0,
            "pdf_drawing_count": 0,
            "visual_signal_pages": [],
            "chart_candidate_pages": [],
            "visual_signal_error_reason": str(exc),
        }
    return {
        "pdf_image_count": int(signals.get("pdf_image_count") or 0),
        "pdf_drawing_count": int(signals.get("pdf_drawing_count") or 0),
        "visual_signal_pages": list(signals.get("visual_signal_pages") or []),
        "chart_candidate_pages": list(signals.get("chart_candidate_pages") or []),
        "visual_signal_error_reason": None,
    }


def _quality_score(
    *,
    text_pdf_token_f1: float,
    key_term_recall: float,
    table_like_recall: float,
    page_citation_available: bool,
    visual_content_present: bool,
) -> float:
    citation_score = 1.0 if page_citation_available else 0.0
    visual_score = 0.6 if visual_content_present else 1.0
    score = (
        0.45 * text_pdf_token_f1
        + 0.20 * key_term_recall
        + 0.15 * table_like_recall
        + 0.15 * citation_score
        + 0.05 * visual_score
    )
    return round(score, 4)


def _risk_flags(
    *,
    parsed_text: str,
    page_text: str,
    token_f1: float,
    page_citation_available: bool,
    table_like_page_line_count: int,
    table_like_recall: float,
    visual_content_present: bool,
    chart_candidate_pages: list[int],
) -> list[str]:
    flags: list[str] = []
    if not parsed_text:
        flags.append("missing_parsed_text")
    if not page_text:
        flags.append("missing_page_text")
    if page_text and token_f1 < 0.45:
        flags.append("low_text_pdf_overlap")
    if not page_citation_available:
        flags.append("citation_unavailable")
    if table_like_page_line_count and table_like_recall < 0.5:
        flags.append("table_signal_loss")
    if visual_content_present:
        flags.append("visual_content_present")
        flags.append("visual_content_unparsed")
    if chart_candidate_pages:
        flags.append("chart_or_drawing_signal_present")
    return flags


def evaluate_parse_record(
    record: dict[str, Any],
    *,
    pdf_visual_analyzer: PdfVisualAnalyzer = _pdf_visual_signals,
) -> dict[str, Any]:
    parsed_text = _read_text_path(record.get("text_path"))
    page_text, page_text_page_count = _read_page_text_path(record.get("page_text_path"))
    overlap = _token_overlap(parsed_text, page_text)
    key_term_recall = _key_term_recall(parsed_text, page_text)
    table_like_page_line_count = _table_like_line_count(page_text)
    table_like_parsed_line_count = _table_like_line_count(parsed_text)
    table_like_recall = (
        1.0
        if table_like_page_line_count == 0
        else round(min(table_like_parsed_line_count / table_like_page_line_count, 1.0), 4)
    )
    visual_signals = _safe_pdf_visual_signals(record.get("converted_pdf_path"), pdf_visual_analyzer)
    visual_content_present = bool(visual_signals["pdf_image_count"] or visual_signals["pdf_drawing_count"])
    page_citation_available = bool(record.get("page_citation_available"))
    risk_flags = _risk_flags(
        parsed_text=parsed_text,
        page_text=page_text,
        token_f1=overlap["text_pdf_token_f1"],
        page_citation_available=page_citation_available,
        table_like_page_line_count=table_like_page_line_count,
        table_like_recall=table_like_recall,
        visual_content_present=visual_content_present,
        chart_candidate_pages=visual_signals["chart_candidate_pages"],
    )
    quality_score = _quality_score(
        text_pdf_token_f1=overlap["text_pdf_token_f1"],
        key_term_recall=key_term_recall,
        table_like_recall=table_like_recall,
        page_citation_available=page_citation_available,
        visual_content_present=visual_content_present,
    )
    return {
        "doc_id": record.get("doc_id"),
        "parse_status": record.get("parse_status"),
        "parser_backend": record.get("parser_backend"),
        "content_source": record.get("content_source"),
        "source_quality": record.get("source_quality"),
        "citation_level": record.get("citation_level"),
        "page_citation_available": page_citation_available,
        "parsed_text_length": len(parsed_text),
        "page_text_length": len(page_text),
        "page_text_page_count": page_text_page_count,
        **overlap,
        "key_term_recall": key_term_recall,
        "table_like_page_line_count": table_like_page_line_count,
        "table_like_parsed_line_count": table_like_parsed_line_count,
        "table_like_recall": table_like_recall,
        **visual_signals,
        "visual_content_present": visual_content_present,
        "quality_score": quality_score,
        "risk_flags": risk_flags,
    }


def summarize_quality_records(
    records: Iterable[dict[str, Any]],
    *,
    quality_threshold: float = 0.6,
) -> dict[str, Any]:
    rows = list(records)
    flag_counts = Counter(flag for row in rows for flag in row.get("risk_flags", []))
    low_quality_count = sum(1 for row in rows if float(row.get("quality_score") or 0.0) < quality_threshold)
    citation_count = sum(1 for row in rows if row.get("page_citation_available") is True)
    visual_doc_count = sum(1 for row in rows if row.get("visual_content_present") is True)
    average_quality_score = round(mean(float(row.get("quality_score") or 0.0) for row in rows), 4) if rows else 0.0
    return {
        "doc_count": len(rows),
        "quality_threshold": quality_threshold,
        "average_quality_score": average_quality_score,
        "low_quality_doc_count": low_quality_count,
        "page_citation_available_count": citation_count,
        "page_citation_coverage": round(citation_count / len(rows), 4) if rows else 0.0,
        "visual_content_doc_count": visual_doc_count,
        "risk_flag_counts": dict(sorted(flag_counts.items())),
    }


def evaluate_parser_quality(
    parsed_dir: Path | str,
    *,
    quality_threshold: float = 0.6,
    pdf_visual_analyzer: PdfVisualAnalyzer = _pdf_visual_signals,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parsed_path = Path(parsed_dir)
    rows = _read_jsonl(parsed_path / "manifest.jsonl")
    quality_records = [
        evaluate_parse_record(row, pdf_visual_analyzer=pdf_visual_analyzer)
        for row in rows
    ]
    summary = summarize_quality_records(quality_records, quality_threshold=quality_threshold)
    return quality_records, summary


def write_quality_artifacts(
    quality_records: Iterable[dict[str, Any]],
    summary: dict[str, Any],
    out_dir: Path | str,
) -> dict[str, Any]:
    rows = list(quality_records)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "per_doc.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    risky_rows = [
        row
        for row in rows
        if row.get("risk_flags") or float(row.get("quality_score") or 0.0) < float(summary.get("quality_threshold") or 0.6)
    ]
    with (out / "risky_docs.jsonl").open("w", encoding="utf-8") as f:
        for row in risky_rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
