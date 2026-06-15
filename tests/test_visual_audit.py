from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.visual_audit import (
    run_visual_audit,
    select_visual_audit_samples,
    write_visual_audit_artifacts,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def test_select_visual_audit_samples_prioritizes_visual_chart_and_table_risk(
    tmp_path: Path,
) -> None:
    parsed_dir = tmp_path / "parsed"
    pdf_dir = parsed_dir / "pdf"
    page_dir = parsed_dir / "page_text"
    pdf_dir.mkdir(parents=True)
    page_dir.mkdir()
    for idx in range(3):
        (pdf_dir / f"doc_{idx:03d}.pdf").write_bytes(b"%PDF")
        _write_jsonl(
            page_dir / f"doc_{idx:03d}.jsonl", [{"page": 1, "text": "평가 기준"}]
        )
    _write_jsonl(
        parsed_dir / "manifest.jsonl",
        [
            {
                "doc_id": "doc:000",
                "csv_filename_raw": "a.hwp",
                "converted_pdf_path": str(pdf_dir / "doc_000.pdf"),
                "page_text_path": str(page_dir / "doc_000.jsonl"),
                "parser_backend": "unhwp",
            },
            {
                "doc_id": "doc:001",
                "csv_filename_raw": "b.hwp",
                "converted_pdf_path": str(pdf_dir / "doc_001.pdf"),
                "page_text_path": str(page_dir / "doc_001.jsonl"),
                "parser_backend": "unhwp",
            },
            {
                "doc_id": "doc:002",
                "csv_filename_raw": "c.pdf",
                "converted_pdf_path": str(pdf_dir / "doc_002.pdf"),
                "page_text_path": str(page_dir / "doc_002.jsonl"),
                "parser_backend": "pymupdf",
            },
        ],
    )
    quality_rows = [
        {
            "doc_id": "doc:000",
            "quality_score": 0.98,
            "table_like_recall": 1.0,
            "pdf_image_count": 3,
            "pdf_drawing_count": 20,
            "visual_signal_pages": [1],
            "chart_candidate_pages": [1],
            "risk_flags": ["visual_content_present", "chart_or_drawing_signal_present"],
        },
        {
            "doc_id": "doc:001",
            "quality_score": 0.84,
            "table_like_recall": 0.4,
            "pdf_image_count": 1,
            "pdf_drawing_count": 40,
            "visual_signal_pages": [2, 3],
            "chart_candidate_pages": [3],
            "risk_flags": [
                "visual_content_present",
                "chart_or_drawing_signal_present",
                "table_signal_loss",
            ],
        },
        {
            "doc_id": "doc:002",
            "quality_score": 0.99,
            "table_like_recall": 1.0,
            "pdf_image_count": 0,
            "pdf_drawing_count": 0,
            "visual_signal_pages": [],
            "chart_candidate_pages": [],
            "risk_flags": [],
        },
    ]

    samples, summary = select_visual_audit_samples(
        parsed_dir, quality_rows, max_docs=2, max_pages_per_doc=1
    )

    assert [sample["doc_id"] for sample in samples] == ["doc:001", "doc:000"]
    assert samples[0]["selected_pages"] == [3]
    assert samples[0]["visual_parse_decision"] == "manual_audit_required"
    assert "table_signal_loss" in samples[0]["audit_reasons"]
    assert samples[0]["review_questions"][0].startswith("선택 페이지")
    assert summary["sample_count"] == 2
    assert summary["candidate_count"] == 2
    assert summary["visual_only_answer_risk"] == "unknown_until_manual_audit"


def test_select_visual_audit_samples_preserves_zero_quality_metrics(
    tmp_path: Path,
) -> None:
    parsed_dir = tmp_path / "parsed"
    pdf_dir = parsed_dir / "pdf"
    pdf_dir.mkdir(parents=True)
    pdf_path = pdf_dir / "doc_000.pdf"
    pdf_path.write_bytes(b"%PDF")
    _write_jsonl(
        parsed_dir / "manifest.jsonl",
        [
            {
                "doc_id": "doc:000",
                "csv_filename_raw": "a.hwp",
                "converted_pdf_path": str(pdf_path),
                "page_text_path": str(parsed_dir / "page_text" / "doc_000.jsonl"),
                "parser_backend": "unhwp",
            }
        ],
    )
    quality_rows = [
        {
            "doc_id": "doc:000",
            "quality_score": 0.0,
            "table_like_recall": 0.0,
            "pdf_image_count": 0,
            "pdf_drawing_count": 0,
            "visual_signal_pages": [],
            "chart_candidate_pages": [],
            "risk_flags": [],
        }
    ]

    samples, summary = select_visual_audit_samples(parsed_dir, quality_rows, max_docs=1)

    assert summary["sample_count"] == 1
    assert samples[0]["audit_reasons"] == ["table_signal_loss", "lower_parser_quality"]
    assert samples[0]["audit_priority_score"] == 15.0


def test_write_visual_audit_artifacts_writes_jsonl_summary_and_review(
    tmp_path: Path,
) -> None:
    samples = [
        {
            "rank": 1,
            "doc_id": "doc:001",
            "source_filename": "b.hwp",
            "pdf_path": "/tmp/doc_001.pdf",
            "selected_pages": [3],
            "audit_priority_score": 12.5,
            "audit_reasons": ["chart_or_drawing_signal_present"],
            "review_questions": ["선택 페이지의 시각 요소가 입찰 검토 정보인가?"],
        }
    ]
    summary = {"sample_count": 1, "candidate_count": 1}

    write_visual_audit_artifacts(samples, summary, tmp_path / "visual_audit")

    assert (tmp_path / "visual_audit" / "samples.jsonl").is_file()
    saved_summary = json.loads(
        (tmp_path / "visual_audit" / "summary.json").read_text(encoding="utf-8")
    )
    assert saved_summary["sample_count"] == 1
    review = (tmp_path / "visual_audit" / "review.md").read_text(encoding="utf-8")
    assert "doc:001" in review
    assert "/tmp/doc_001.pdf" in review
    assert "선택 페이지의 시각 요소" in review


def test_run_visual_audit_reads_quality_artifacts_and_writes_outputs(
    tmp_path: Path,
) -> None:
    parsed_dir = tmp_path / "parsed"
    quality_dir = tmp_path / "quality"
    pdf_dir = parsed_dir / "pdf"
    pdf_dir.mkdir(parents=True)
    pdf_path = pdf_dir / "doc_000.pdf"
    pdf_path.write_bytes(b"%PDF")
    _write_jsonl(
        parsed_dir / "manifest.jsonl",
        [
            {
                "doc_id": "doc:000",
                "csv_filename_raw": "a.hwp",
                "converted_pdf_path": str(pdf_path),
                "page_text_path": str(parsed_dir / "page_text" / "doc_000.jsonl"),
                "parser_backend": "unhwp",
            }
        ],
    )
    _write_jsonl(
        quality_dir / "per_doc.jsonl",
        [
            {
                "doc_id": "doc:000",
                "quality_score": 0.9,
                "table_like_recall": 1.0,
                "pdf_image_count": 1,
                "pdf_drawing_count": 15,
                "visual_signal_pages": [1, 2],
                "chart_candidate_pages": [2],
                "risk_flags": [
                    "visual_content_present",
                    "chart_or_drawing_signal_present",
                ],
            }
        ],
    )

    summary = run_visual_audit(
        parsed_dir, quality_dir, tmp_path / "out", max_docs=1, max_pages_per_doc=2
    )

    assert summary["sample_count"] == 1
    assert (tmp_path / "out" / "samples.jsonl").is_file()
    sample = json.loads(
        (tmp_path / "out" / "samples.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert sample["doc_id"] == "doc:000"
    assert sample["selected_pages"] == [2, 1]
