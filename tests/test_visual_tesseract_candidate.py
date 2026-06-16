from __future__ import annotations

import json
from pathlib import Path

import rfp_rag.visual_tesseract_candidate as visual_tesseract_candidate
from rfp_rag.visual_tesseract_candidate import (
    build_visual_tesseract_candidates,
    run_visual_tesseract_candidate,
)


def _records() -> list[dict]:
    return [
        {
            "record_id": "doc:001:p3:gantt_schedule",
            "doc_id": "doc:001",
            "page": 3,
            "visual_type": "gantt_schedule",
            "business_fields": ["schedule"],
            "review_status": "reviewed_needs_extraction",
            "evidence_ref": {"pdf_path": "artifacts/parsed_docs/pdf/doc_001.pdf"},
        },
        {
            "record_id": "doc:002:p5:system_architecture_diagram",
            "doc_id": "doc:002",
            "page": 5,
            "visual_type": "system_architecture_diagram",
            "business_fields": ["system_architecture"],
            "review_status": "reviewed_needs_extraction",
            "evidence_ref": {"pdf_path": "artifacts/parsed_docs/pdf/doc_002.pdf"},
        },
        {
            "record_id": "doc:003:p7:organization_chart",
            "doc_id": "doc:003",
            "page": 7,
            "visual_type": "organization_chart",
            "business_fields": ["requirements"],
            "review_status": "reviewed_needs_extraction",
            "evidence_ref": {"pdf_path": "artifacts/parsed_docs/pdf/doc_003.pdf"},
        },
        {
            "record_id": "doc:004:p9:requirements_table",
            "doc_id": "doc:004",
            "page": 9,
            "visual_type": "requirements_table",
            "business_fields": ["requirements"],
            "review_status": "reviewed_needs_extraction",
            "evidence_ref": {"pdf_path": "artifacts/parsed_docs/pdf/doc_004.pdf"},
        },
        {
            "record_id": "doc:005:p1:gantt_schedule",
            "doc_id": "doc:005",
            "page": 1,
            "visual_type": "gantt_schedule",
            "business_fields": ["schedule"],
            "review_status": "needs_page_review",
            "evidence_ref": {"pdf_path": "artifacts/parsed_docs/pdf/doc_005.pdf"},
        },
    ]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def test_build_visual_tesseract_candidates_maps_keywords_to_gold_contract() -> None:
    ocr_text_by_record = {
        "doc:001:p3:gantt_schedule": "착수 완료 일정 계획 1개월 2개월",
        "doc:002:p5:system_architecture_diagram": "시스템 구성 서버 DB 연계",
        "doc:003:p7:organization_chart": "수행체계 PM 사업관리팀 역할",
        "doc:004:p9:requirements_table": "요구사항 기능 항목 세부 내용",
        "doc:005:p1:gantt_schedule": "일정",
    }

    candidates, summary, observations = build_visual_tesseract_candidates(
        _records(), ocr_text_by_record
    )

    assert [(c["record_id"], c["fact_type"], c["field"]) for c in candidates] == [
        ("doc:001:p3:gantt_schedule", "visual_type_present", "schedule"),
        (
            "doc:002:p5:system_architecture_diagram",
            "visual_type_present",
            "system_architecture",
        ),
        (
            "doc:003:p7:organization_chart",
            "business_field_affected",
            "requirements",
        ),
    ]
    assert {c["extractor"] for c in candidates} == {"visual_tesseract_ocr_candidate_v2"}
    assert summary["candidate_fact_count"] == 3
    assert summary["skipped_record_count"] == 1
    assert summary["ocr_text_record_count"] == 5
    assert observations[0]["matched_keywords"]


def test_build_visual_tesseract_candidates_skips_empty_or_keywordless_ocr() -> None:
    candidates, summary, observations = build_visual_tesseract_candidates(
        _records(),
        {
            "doc:001:p3:gantt_schedule": "",
            "doc:002:p5:system_architecture_diagram": "본문 텍스트만 있음",
            "doc:003:p7:organization_chart": "조직",
            "doc:004:p9:requirements_table": "요구사항",
        },
    )

    assert [(c["record_id"], c["fact_type"], c["field"]) for c in candidates] == [
        (
            "doc:003:p7:organization_chart",
            "business_field_affected",
            "requirements",
        ),
    ]
    assert summary["candidate_fact_count"] == 1
    assert summary["no_keyword_match_count"] == 1
    assert summary["empty_ocr_text_count"] == 1
    assert summary["insufficient_ocr_evidence_count"] == 1
    assert observations[0]["status"] == "empty_ocr_text"


def test_build_visual_tesseract_candidates_filters_weak_ocr_evidence() -> None:
    records = [
        {
            "record_id": "doc:101:p1:gantt_schedule",
            "doc_id": "doc:101",
            "page": 1,
            "visual_type": "gantt_schedule",
            "review_status": "reviewed_needs_extraction",
            "evidence_ref": {"pdf_path": "artifacts/parsed_docs/pdf/doc_101.pdf"},
        },
        {
            "record_id": "doc:101:p2:gantt_schedule",
            "doc_id": "doc:101",
            "page": 2,
            "visual_type": "gantt_schedule",
            "review_status": "reviewed_needs_extraction",
            "evidence_ref": {"pdf_path": "artifacts/parsed_docs/pdf/doc_101.pdf"},
        },
        {
            "record_id": "doc:102:p1:system_architecture_diagram",
            "doc_id": "doc:102",
            "page": 1,
            "visual_type": "system_architecture_diagram",
            "review_status": "reviewed_needs_extraction",
            "evidence_ref": {"pdf_path": "artifacts/parsed_docs/pdf/doc_102.pdf"},
        },
        {
            "record_id": "doc:102:p2:system_architecture_diagram",
            "doc_id": "doc:102",
            "page": 2,
            "visual_type": "system_architecture_diagram",
            "review_status": "reviewed_needs_extraction",
            "evidence_ref": {"pdf_path": "artifacts/parsed_docs/pdf/doc_102.pdf"},
        },
        {
            "record_id": "doc:102:p3:system_architecture_diagram",
            "doc_id": "doc:102",
            "page": 3,
            "visual_type": "system_architecture_diagram",
            "review_status": "reviewed_needs_extraction",
            "evidence_ref": {"pdf_path": "artifacts/parsed_docs/pdf/doc_102.pdf"},
        },
        {
            "record_id": "doc:103:p1:organization_chart",
            "doc_id": "doc:103",
            "page": 1,
            "visual_type": "organization_chart",
            "review_status": "reviewed_needs_extraction",
            "evidence_ref": {"pdf_path": "artifacts/parsed_docs/pdf/doc_103.pdf"},
        },
        {
            "record_id": "doc:103:p2:organization_chart",
            "doc_id": "doc:103",
            "page": 2,
            "visual_type": "organization_chart",
            "review_status": "reviewed_needs_extraction",
            "evidence_ref": {"pdf_path": "artifacts/parsed_docs/pdf/doc_103.pdf"},
        },
        {
            "record_id": "doc:104:p1:requirements_table",
            "doc_id": "doc:104",
            "page": 1,
            "visual_type": "requirements_table",
            "review_status": "reviewed_needs_extraction",
            "evidence_ref": {"pdf_path": "artifacts/parsed_docs/pdf/doc_104.pdf"},
        },
    ]

    candidates, summary, observations = build_visual_tesseract_candidates(
        records,
        {
            "doc:101:p1:gantt_schedule": "일정 추진일정",
            "doc:101:p2:gantt_schedule": "일정 추진일정 계획",
            "doc:102:p1:system_architecture_diagram": "시스템 구성",
            "doc:102:p2:system_architecture_diagram": "시스템 구성 서버",
            "doc:102:p3:system_architecture_diagram": "연계",
            "doc:103:p1:organization_chart": "추진체계 PM 팀",
            "doc:103:p2:organization_chart": "수행체계 PM",
            "doc:104:p1:requirements_table": "요구사항 기능 항목 세부 내용",
        },
    )

    assert [(c["record_id"], c["field"]) for c in candidates] == [
        ("doc:101:p2:gantt_schedule", "schedule"),
        ("doc:102:p2:system_architecture_diagram", "system_architecture"),
        ("doc:102:p3:system_architecture_diagram", "system_architecture"),
        ("doc:103:p2:organization_chart", "requirements"),
    ]
    assert summary["candidate_fact_count"] == 4
    assert summary["insufficient_ocr_evidence_count"] == 4
    assert [
        observation["record_id"]
        for observation in observations
        if observation["status"] == "insufficient_ocr_evidence"
    ] == [
        "doc:101:p1:gantt_schedule",
        "doc:102:p1:system_architecture_diagram",
        "doc:103:p1:organization_chart",
        "doc:104:p1:requirements_table",
    ]


def test_build_visual_tesseract_candidates_can_include_page_review_records() -> None:
    candidates, summary, observations = build_visual_tesseract_candidates(
        _records(),
        {
            "doc:001:p3:gantt_schedule": "착수 완료 일정 계획",
            "doc:005:p1:gantt_schedule": "일정 추진일정 착수",
        },
        review_statuses=("reviewed_needs_extraction", "needs_page_review"),
    )

    assert [(c["record_id"], c["field"]) for c in candidates] == [
        ("doc:001:p3:gantt_schedule", "schedule"),
        ("doc:005:p1:gantt_schedule", "schedule"),
    ]
    assert summary["review_status_filter"] == [
        "needs_page_review",
        "reviewed_needs_extraction",
    ]
    assert summary["candidate_fact_count"] == 2
    assert not [
        observation
        for observation in observations
        if observation["status"] == "skipped_review_status"
    ]


def test_run_visual_tesseract_candidate_writes_artifacts_from_ocr_text_fixture(
    tmp_path: Path,
) -> None:
    records_path = tmp_path / "records.jsonl"
    ocr_text_path = tmp_path / "ocr_text.jsonl"
    out_dir = tmp_path / "out"
    _write_jsonl(records_path, _records())
    _write_jsonl(
        ocr_text_path,
        [
            {
                "record_id": "doc:001:p3:gantt_schedule",
                "text": "착수 완료 일정 계획",
            },
            {
                "record_id": "doc:003:p7:organization_chart",
                "text": "수행체계 PM 역할",
            },
        ],
    )

    summary = run_visual_tesseract_candidate(
        records_path, out_dir, ocr_text_path=ocr_text_path
    )

    assert summary["candidate_fact_count"] == 2
    assert (out_dir / "candidate_facts.jsonl").is_file()
    assert (out_dir / "observations.jsonl").is_file()
    assert (out_dir / "summary.json").is_file()


def test_ocr_records_reuses_rendered_text_for_same_pdf_page(
    tmp_path: Path, monkeypatch
) -> None:
    image_path = tmp_path / "page.ppm"
    image_path.write_bytes(b"P6\n1 1\n255\n\xff\xff\xff")
    render_calls: list[tuple[str, int]] = []
    tesseract_calls: list[Path] = []

    def fake_render(record: dict, work_dir: Path, **kwargs) -> Path:
        render_calls.append((record["record_id"], record["page"]))
        return image_path

    def fake_tesseract(path: Path, **kwargs) -> str:
        tesseract_calls.append(path)
        return "시스템 구성"

    monkeypatch.setattr(visual_tesseract_candidate, "_render_page_ppm", fake_render)
    monkeypatch.setattr(
        visual_tesseract_candidate, "_run_tesseract_stdin", fake_tesseract
    )

    records = [
        {
            "record_id": "doc:001:p5:system_architecture_diagram",
            "page": 5,
            "review_status": "reviewed_needs_extraction",
            "evidence_ref": {"pdf_path": "same.pdf"},
        },
        {
            "record_id": "doc:001:p5:gantt_schedule",
            "page": 5,
            "review_status": "reviewed_needs_extraction",
            "evidence_ref": {"pdf_path": "same.pdf"},
        },
    ]

    ocr_text_by_record, observations = visual_tesseract_candidate._ocr_records(
        records,
        dpi=120,
        lang="kor+eng",
        psm=11,
        pdftoppm_bin="pdftoppm",
        tesseract_bin="tesseract",
        timeout_seconds=8,
    )

    assert render_calls == [("doc:001:p5:system_architecture_diagram", 5)]
    assert tesseract_calls == [image_path]
    assert ocr_text_by_record == {
        "doc:001:p5:system_architecture_diagram": "시스템 구성",
        "doc:001:p5:gantt_schedule": "시스템 구성",
    }
    assert observations == []


def test_run_visual_tesseract_candidate_cli_accepts_ocr_text_fixture(
    tmp_path: Path, capsys
) -> None:
    from rfp_rag.run_visual_tesseract_candidate import main

    records_path = tmp_path / "records.jsonl"
    ocr_text_path = tmp_path / "ocr_text.jsonl"
    out_dir = tmp_path / "out"
    _write_jsonl(records_path, _records())
    _write_jsonl(
        ocr_text_path,
        [
            {
                "record_id": "doc:002:p5:system_architecture_diagram",
                "text": "시스템 구성 서버",
            }
        ],
    )

    assert (
        main(
            [
                "--records",
                str(records_path),
                "--out",
                str(out_dir),
                "--ocr-text",
                str(ocr_text_path),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["candidate_fact_count"] == 1


def test_run_visual_tesseract_candidate_cli_accepts_repeated_review_status(
    tmp_path: Path, capsys
) -> None:
    from rfp_rag.run_visual_tesseract_candidate import main

    records_path = tmp_path / "records.jsonl"
    ocr_text_path = tmp_path / "ocr_text.jsonl"
    out_dir = tmp_path / "out"
    _write_jsonl(records_path, _records())
    _write_jsonl(
        ocr_text_path,
        [
            {
                "record_id": "doc:005:p1:gantt_schedule",
                "text": "일정 추진일정 착수",
            }
        ],
    )

    assert (
        main(
            [
                "--records",
                str(records_path),
                "--out",
                str(out_dir),
                "--ocr-text",
                str(ocr_text_path),
                "--review-status",
                "reviewed_needs_extraction",
                "--review-status",
                "needs_page_review",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["review_status_filter"] == [
        "needs_page_review",
        "reviewed_needs_extraction",
    ]
    assert payload["candidate_fact_count"] == 1
