from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.parser_quality_eval import (
    evaluate_parse_record,
    evaluate_parser_quality,
    summarize_quality_records,
    write_quality_artifacts,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def test_evaluate_parse_record_scores_text_page_table_and_visual_signals(
    tmp_path: Path,
) -> None:
    parsed_text = tmp_path / "text" / "doc_000.txt"
    parsed_text.parent.mkdir()
    parsed_text.write_text(
        "사업개요 예산 제출 평가 기준 요구사항\nREQ-001 | 기능 | 설명\n",
        encoding="utf-8",
    )
    page_text = tmp_path / "page_text" / "doc_000.jsonl"
    _write_jsonl(
        page_text,
        [
            {"page": 1, "text": "사업개요 예산 제출 평가 기준 요구사항"},
            {"page": 2, "text": "REQ-001 | 기능 | 설명\nREQ-002 | 보안 | 암호화"},
        ],
    )
    pdf_path = tmp_path / "pdf" / "doc_000.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF")
    record = {
        "doc_id": "doc:000",
        "parse_status": "parsed",
        "parser_backend": "unhwp",
        "text_path": str(parsed_text),
        "page_text_path": str(page_text),
        "converted_pdf_path": str(pdf_path),
        "page_citation_available": True,
        "citation_level": "page",
        "page_count": 2,
        "content_source": "source_hwp_text",
        "source_quality": "source_parsed",
    }

    quality = evaluate_parse_record(
        record,
        pdf_visual_analyzer=lambda path: {
            "pdf_image_count": 1,
            "pdf_drawing_count": 24,
            "visual_signal_pages": [2],
            "chart_candidate_pages": [2],
        },
    )

    assert quality["doc_id"] == "doc:000"
    assert quality["parser_backend"] == "unhwp"
    assert quality["page_citation_available"] is True
    assert quality["text_pdf_token_recall"] == 0.7692
    assert quality["text_pdf_token_precision"] == 1.0
    assert quality["key_term_recall"] == 0.8333
    assert quality["table_like_page_line_count"] == 2
    assert quality["table_like_parsed_line_count"] == 1
    assert quality["table_like_recall"] == 0.5
    assert quality["visual_content_present"] is True
    assert quality["chart_candidate_pages"] == [2]
    assert "visual_content_present" in quality["risk_flags"]
    assert "chart_or_drawing_signal_present" in quality["risk_flags"]
    assert "table_signal_loss" not in quality["risk_flags"]
    assert 0.7 <= quality["quality_score"] <= 1.0


def test_evaluate_parse_record_flags_low_quality_and_missing_page_text(
    tmp_path: Path,
) -> None:
    parsed_text = tmp_path / "text" / "doc_001.txt"
    parsed_text.parent.mkdir()
    parsed_text.write_text("전혀 다른 짧은 내용", encoding="utf-8")
    record = {
        "doc_id": "doc:001",
        "parse_status": "parsed",
        "parser_backend": "hwp5txt",
        "text_path": str(parsed_text),
        "page_text_path": None,
        "converted_pdf_path": None,
        "page_citation_available": False,
        "citation_level": "document",
    }

    quality = evaluate_parse_record(record)

    assert quality["quality_score"] < 0.5
    assert quality["text_pdf_token_f1"] == 0.0
    assert quality["risk_flags"] == [
        "missing_page_text",
        "citation_unavailable",
    ]


def test_evaluate_parser_quality_writes_summary_and_risky_docs(tmp_path: Path) -> None:
    parsed_dir = tmp_path / "parsed"
    text_dir = parsed_dir / "text"
    page_dir = parsed_dir / "page_text"
    text_dir.mkdir(parents=True)
    page_dir.mkdir()
    (text_dir / "doc_000.txt").write_text(
        "사업개요 예산 제출 평가 기준 요구사항", encoding="utf-8"
    )
    _write_jsonl(
        page_dir / "doc_000.jsonl",
        [{"page": 1, "text": "사업개요 예산 제출 평가 기준 요구사항"}],
    )
    (text_dir / "doc_001.txt").write_text("", encoding="utf-8")
    manifest_rows = [
        {
            "doc_id": "doc:000",
            "parse_status": "parsed",
            "parser_backend": "unhwp",
            "text_path": str(text_dir / "doc_000.txt"),
            "page_text_path": str(page_dir / "doc_000.jsonl"),
            "converted_pdf_path": None,
            "page_citation_available": True,
            "citation_level": "page",
        },
        {
            "doc_id": "doc:001",
            "parse_status": "empty_text",
            "parser_backend": "hwp5txt",
            "text_path": str(text_dir / "doc_001.txt"),
            "page_text_path": None,
            "converted_pdf_path": None,
            "page_citation_available": False,
            "citation_level": "none",
        },
    ]
    _write_jsonl(parsed_dir / "manifest.jsonl", manifest_rows)

    quality_records, summary = evaluate_parser_quality(
        parsed_dir, quality_threshold=0.6
    )
    out_summary = write_quality_artifacts(
        quality_records, summary, tmp_path / "quality"
    )

    assert summary["doc_count"] == 2
    assert summary["page_citation_coverage"] == 0.5
    assert summary["low_quality_doc_count"] == 1
    assert summary["risk_flag_counts"]["missing_parsed_text"] == 1
    assert out_summary == summary
    assert (tmp_path / "quality" / "per_doc.jsonl").is_file()
    risky_rows = [
        json.loads(line)
        for line in (tmp_path / "quality" / "risky_docs.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [row["doc_id"] for row in risky_rows] == ["doc:001"]


def test_summarize_quality_records_counts_visual_and_table_risks() -> None:
    summary = summarize_quality_records(
        [
            {
                "quality_score": 0.9,
                "page_citation_available": True,
                "visual_content_present": True,
                "risk_flags": ["visual_content_present"],
            },
            {
                "quality_score": 0.2,
                "page_citation_available": False,
                "visual_content_present": False,
                "risk_flags": ["missing_page_text", "table_signal_loss"],
            },
        ],
        quality_threshold=0.6,
    )

    assert summary["doc_count"] == 2
    assert summary["average_quality_score"] == 0.55
    assert summary["page_citation_coverage"] == 0.5
    assert summary["visual_content_doc_count"] == 1
    assert summary["low_quality_doc_count"] == 1
    assert summary["risk_flag_counts"] == {
        "missing_page_text": 1,
        "table_signal_loss": 1,
        "visual_content_present": 1,
    }
