from __future__ import annotations

import json
import subprocess
from pathlib import Path

import rfp_rag.source_parsing as source_parsing
from rfp_rag.corpus import CorpusDocument
from rfp_rag.source_parsing import (
    PARSE_EMPTY_TEXT,
    PARSE_MISSING_SOURCE_FILE,
    PARSE_PARSED,
    PARSE_PARSER_ERROR,
    PARSE_TIMEOUT,
    PARSE_UNSUPPORTED_SUFFIX,
    ParseResult,
    build_parse_record,
    parse_document_source,
    parse_hwp_file,
    safe_doc_filename,
    summarize_records,
    write_parse_artifacts,
)


def _doc(path: Path | None, text: str = "CSV 본문") -> CorpusDocument:
    return CorpusDocument(
        csv_row_id="000",
        doc_id="doc:000",
        text=text,
        metadata={
            "project_name": "테스트 사업",
            "issuer": "테스트기관",
            "resolved_filesystem_path": None if path is None else str(path),
            "csv_filename_raw": "" if path is None else path.name,
        },
    )


def test_safe_doc_filename_replaces_colon() -> None:
    assert safe_doc_filename("doc:000") == "doc_000.txt"


def test_parse_hwp_file_success_keeps_stderr_diagnostics(tmp_path: Path) -> None:
    source = tmp_path / "sample.hwp"
    source.write_bytes(b"fake")

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="  본문\n", stderr="warning"
        )

    result = parse_hwp_file(source, timeout_seconds=5, runner=runner)

    assert result.status == PARSE_PARSED
    assert result.parser_backend == "hwp5txt"
    assert result.text == "본문"
    assert result.stderr == "warning"
    assert result.error_reason is None


def test_parse_hwp_file_empty_stdout_is_empty_text(tmp_path: Path) -> None:
    source = tmp_path / "sample.hwp"
    source.write_bytes(b"fake")

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout=" \n ", stderr=""
        )

    result = parse_hwp_file(source, timeout_seconds=5, runner=runner)

    assert result.status == PARSE_EMPTY_TEXT
    assert result.text == ""
    assert result.error_reason == "empty stdout"


def test_parse_hwp_file_nonzero_exit_is_parser_error(tmp_path: Path) -> None:
    source = tmp_path / "sample.hwp"
    source.write_bytes(b"fake")

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=2, stdout="", stderr="boom"
        )

    result = parse_hwp_file(source, timeout_seconds=5, runner=runner)

    assert result.status == PARSE_PARSER_ERROR
    assert result.error_reason == "hwp5txt exited 2"
    assert result.stderr == "boom"


def test_parse_hwp_file_timeout_is_recorded(tmp_path: Path) -> None:
    source = tmp_path / "sample.hwp"
    source.write_bytes(b"fake")

    def runner(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=5)

    result = parse_hwp_file(source, timeout_seconds=5, runner=runner)

    assert result.status == PARSE_TIMEOUT
    assert result.error_reason == "parser timeout after 5s"


def test_parse_hwp_file_with_fallbacks_prefers_unhwp(tmp_path: Path) -> None:
    source = tmp_path / "sample.hwp"
    source.write_bytes(b"fake")
    calls: list[list[str]] = []

    def finder(name: str, *, extra_candidates=()):
        return f"/bin/{name}"

    def runner(command, **kwargs):
        calls.append(command)
        assert command[0] == "/bin/unhwp"
        return subprocess.CompletedProcess(command, 0, stdout="unhwp 본문", stderr="")

    result = source_parsing.parse_hwp_file_with_fallbacks(
        source,
        doc_id="doc:000",
        out_dir=tmp_path / "parsed",
        timeout_seconds=5,
        runner=runner,
        executable_finder=finder,
    )

    assert result.status == PARSE_PARSED
    assert result.parser_backend == "unhwp"
    assert result.text == "unhwp 본문"
    assert result.content_source == "source_hwp_text"
    assert result.source_quality == "source_parsed"
    assert result.attempts == [
        {
            "backend": "unhwp",
            "status": PARSE_PARSED,
            "text_length": len("unhwp 본문"),
            "error_reason": None,
        }
    ]
    assert len(calls) == 1


def test_parse_hwp_file_with_fallbacks_uses_hwp5txt_after_unhwp_failure(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.hwp"
    source.write_bytes(b"fake")

    def finder(name: str, *, extra_candidates=()):
        return f"/bin/{name}"

    def runner(command, **kwargs):
        if command[0] == "/bin/unhwp":
            return subprocess.CompletedProcess(
                command, 2, stdout="", stderr="unhwp fail"
            )
        return subprocess.CompletedProcess(command, 0, stdout="hwp5txt 본문", stderr="")

    result = source_parsing.parse_hwp_file_with_fallbacks(
        source,
        doc_id="doc:000",
        out_dir=tmp_path / "parsed",
        timeout_seconds=5,
        runner=runner,
        executable_finder=finder,
    )

    assert result.status == PARSE_PARSED
    assert result.parser_backend == "hwp5txt"
    assert result.text == "hwp5txt 본문"
    assert [attempt["backend"] for attempt in result.attempts or []] == [
        "unhwp",
        "hwp5txt",
    ]
    assert result.attempts[0]["status"] == PARSE_PARSER_ERROR
    assert result.attempts[1]["status"] == PARSE_PARSED


def test_parse_hwp_file_with_fallbacks_uses_converted_pdf_after_text_backends(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.hwp"
    source.write_bytes(b"fake")
    out_dir = tmp_path / "parsed"

    def finder(name: str, *, extra_candidates=()):
        return f"/bin/{name}"

    def runner(command, **kwargs):
        if command[0] == "/bin/unhwp":
            return subprocess.CompletedProcess(
                command, 2, stdout="", stderr="unhwp fail"
            )
        if command[0] == "hwp5txt":
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        work_dir = Path(command[command.index("--outdir") + 1])
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "sample.pdf").write_bytes(b"%PDF")
        return subprocess.CompletedProcess(command, 0, stdout="converted", stderr="")

    def pdf_page_text_extractor(pdf_path: Path):
        assert pdf_path == out_dir / "pdf" / "doc_000.pdf"
        return [(1, "PDF 1쪽 본문"), (2, "PDF 2쪽 본문")]

    result = source_parsing.parse_hwp_file_with_fallbacks(
        source,
        doc_id="doc:000",
        out_dir=out_dir,
        timeout_seconds=5,
        runner=runner,
        executable_finder=finder,
        pdf_page_text_extractor=pdf_page_text_extractor,
    )

    assert result.status == PARSE_PARSED
    assert result.parser_backend == "converted_pdf_pymupdf"
    assert result.text == "PDF 1쪽 본문\nPDF 2쪽 본문"
    assert result.content_source == "converted_pdf_text"
    assert result.source_quality == "source_converted_pdf"
    assert [attempt["backend"] for attempt in result.attempts or []] == [
        "unhwp",
        "hwp5txt",
        "converted_pdf_pymupdf",
    ]


def test_parse_hwp_file_with_fallbacks_returns_parser_failure_without_csv_fallback(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.hwp"
    source.write_bytes(b"fake")

    def finder(name: str, *, extra_candidates=()):
        if name == "soffice":
            return None
        return f"/bin/{name}"

    def runner(command, **kwargs):
        if command[0] == "/bin/unhwp":
            return subprocess.CompletedProcess(
                command, 2, stdout="", stderr="unhwp fail"
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = source_parsing.parse_hwp_file_with_fallbacks(
        source,
        doc_id="doc:000",
        out_dir=tmp_path / "parsed",
        timeout_seconds=5,
        runner=runner,
        executable_finder=finder,
    )

    assert result.status == PARSE_PARSER_ERROR
    assert result.parser_backend == "converted_pdf_pymupdf"
    assert result.text == ""
    assert result.content_source is None
    assert result.source_quality is None
    assert [attempt["backend"] for attempt in result.attempts or []] == [
        "unhwp",
        "hwp5txt",
        "converted_pdf_pymupdf",
    ]


def test_parse_document_source_missing_path_is_recorded(tmp_path: Path) -> None:
    no_path_result = parse_document_source(_doc(None))
    missing_file_result = parse_document_source(_doc(tmp_path / "missing.hwp"))

    assert no_path_result.status == PARSE_MISSING_SOURCE_FILE
    assert no_path_result.parser_backend is None
    assert no_path_result.error_reason == "missing source file"
    assert missing_file_result.status == PARSE_MISSING_SOURCE_FILE
    assert missing_file_result.parser_backend is None
    assert missing_file_result.error_reason == "missing source file"


def test_parse_document_source_pdf_uses_pymupdf_text(tmp_path: Path) -> None:
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"fake")

    def pdf_page_text_extractor(pdf_path: Path):
        assert pdf_path == source
        return [(1, "1페이지 본문"), (2, "2페이지 본문")]

    result = parse_document_source(
        _doc(source),
        pdf_page_text_extractor=pdf_page_text_extractor,
    )

    assert result.status == PARSE_PARSED
    assert result.parser_backend == "pymupdf"
    assert result.text == "1페이지 본문\n2페이지 본문"
    assert result.content_source == "source_pdf_text"
    assert result.source_quality == "source_parsed"
    assert result.attempts == [
        {
            "backend": "pymupdf",
            "status": PARSE_PARSED,
            "text_length": len("1페이지 본문\n2페이지 본문"),
            "error_reason": None,
        }
    ]


def test_parse_document_source_unsupported_suffix_is_recorded(tmp_path: Path) -> None:
    source = tmp_path / "sample.docx"
    source.write_bytes(b"fake")

    result = parse_document_source(_doc(source))

    assert result.status == PARSE_UNSUPPORTED_SUFFIX
    assert result.parser_backend is None
    assert result.text == ""
    assert result.error_reason == "unsupported suffix: .docx"


def test_build_parse_record_writes_text_for_parsed_result(tmp_path: Path) -> None:
    source = tmp_path / "sample.hwp"
    source.write_bytes(b"fake")
    out_dir = tmp_path / "parsed"
    record = build_parse_record(
        _doc(source, text="CSV 본문입니다"),
        ParseResult(
            status=PARSE_PARSED,
            parser_backend="hwp5txt",
            text="원문 본문입니다",
            stderr="diagnostic",
            error_reason=None,
        ),
        out_dir,
    )

    assert record["doc_id"] == "doc:000"
    assert record["parse_status"] == PARSE_PARSED
    assert record["text_length"] == len("원문 본문입니다")
    assert record["csv_text_length"] == len("CSV 본문입니다")
    assert record["parsed_to_csv_length_ratio"] == len("원문 본문입니다") / len(
        "CSV 본문입니다"
    )
    assert record["stderr_length"] == len("diagnostic")
    assert record["stderr_sample"] == "diagnostic"
    assert record["text_path"] == str(out_dir / "text" / safe_doc_filename("doc:000"))
    assert Path(record["text_path"]).read_text(encoding="utf-8") == "원문 본문입니다\n"


def test_build_parse_record_preserves_backend_attempts_and_quality(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.hwp"
    source.write_bytes(b"fake")
    attempts = [
        {
            "backend": "unhwp",
            "status": PARSE_PARSER_ERROR,
            "text_length": 0,
            "error_reason": "unhwp exited 2",
        },
        {
            "backend": "converted_pdf_pymupdf",
            "status": PARSE_PARSED,
            "text_length": len("PDF 변환 본문"),
            "error_reason": None,
        },
    ]

    record = build_parse_record(
        _doc(source, text="CSV 메타데이터 텍스트"),
        ParseResult(
            status=PARSE_PARSED,
            parser_backend="converted_pdf_pymupdf",
            text="PDF 변환 본문",
            stderr="",
            error_reason=None,
            attempts=attempts,
            content_source="converted_pdf_text",
            source_quality="source_converted_pdf",
        ),
        tmp_path / "parsed",
    )

    assert record["parser_backend"] == "converted_pdf_pymupdf"
    assert record["content_source"] == "converted_pdf_text"
    assert record["source_quality"] == "source_converted_pdf"
    assert record["text_backend_attempts"] == attempts


def test_build_parse_record_forces_hwp_pdf_page_citation_evidence(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.hwp"
    source.write_bytes(b"fake")
    out_dir = tmp_path / "parsed"

    def citation_runner(command, **kwargs):
        outdir = Path(command[command.index("--outdir") + 1])
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "sample.pdf").write_bytes(b"%PDF")
        return subprocess.CompletedProcess(command, 0, stdout="converted", stderr="")

    def pdf_page_text_extractor(pdf_path: Path):
        assert pdf_path.name == "doc_000.pdf"
        return [(1, "1페이지 본문"), (2, "2페이지 본문")]

    def executable_finder(name: str, *, extra_candidates=()):
        assert name == "soffice"
        assert extra_candidates
        return "soffice"

    record = build_parse_record(
        _doc(source, text="CSV 본문입니다"),
        ParseResult(
            status=PARSE_PARSED,
            parser_backend="hwp5txt",
            text="원문 본문입니다",
            stderr="",
            error_reason=None,
        ),
        out_dir,
        enable_page_citation=True,
        citation_timeout_seconds=5,
        citation_runner=citation_runner,
        executable_finder=executable_finder,
        pdf_page_text_extractor=pdf_page_text_extractor,
    )

    assert record["content_source"] == "source_hwp_text"
    assert record["source_quality"] == "source_parsed"
    assert record["visual_backend"] == "libreoffice_pdf"
    assert record["page_text_backend"] == "pymupdf"
    assert record["page_citation_available"] is True
    assert record["citation_level"] == "page"
    assert record["page_count"] == 2
    assert record["converted_pdf_path"] == str(out_dir / "pdf" / "doc_000.pdf")
    assert record["page_text_path"] == str(out_dir / "page_text" / "doc_000.jsonl")
    page_rows = [
        json.loads(line)
        for line in Path(record["page_text_path"])
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert page_rows == [
        {"page": 1, "text": "1페이지 본문"},
        {"page": 2, "text": "2페이지 본문"},
    ]


def test_build_parse_record_marks_document_citation_when_pdf_conversion_fails(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.hwp"
    source.write_bytes(b"fake")

    def missing_soffice(name: str, *, extra_candidates=()):
        return None

    record = build_parse_record(
        _doc(source),
        ParseResult(
            status=PARSE_PARSED,
            parser_backend="hwp5txt",
            text="원문 본문",
            stderr="",
            error_reason=None,
        ),
        tmp_path / "parsed",
        enable_page_citation=True,
        executable_finder=missing_soffice,
    )

    assert record["page_citation_available"] is False
    assert record["citation_level"] == "document"
    assert record["visual_backend"] is None
    assert record["page_text_backend"] is None
    assert record["page_citation_error_reason"] == "soffice not found"


def test_build_parse_record_marks_unsupported_without_text_file(tmp_path: Path) -> None:
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"fake")
    record = build_parse_record(
        _doc(source),
        ParseResult(
            status=PARSE_UNSUPPORTED_SUFFIX,
            parser_backend=None,
            text="",
            stderr="",
            error_reason="unsupported suffix: .pdf",
        ),
        tmp_path / "parsed",
    )

    assert record["parse_status"] == PARSE_UNSUPPORTED_SUFFIX
    assert record["text_path"] is None
    assert record["error_reason"] == "unsupported suffix: .pdf"


def test_summarize_records_counts_statuses_and_lengths(tmp_path: Path) -> None:
    records = [
        {
            "source_suffix": ".hwp",
            "parser_backend": "hwp5txt",
            "parse_status": PARSE_PARSED,
            "text_length": 100,
            "csv_text_length": 80,
            "parsed_to_csv_length_ratio": 1.25,
            "citation_level": "page",
            "visual_backend": "libreoffice_pdf",
            "page_text_backend": "pymupdf",
            "page_citation_available": True,
            "error_reason": None,
        },
        {
            "source_suffix": ".pdf",
            "parser_backend": None,
            "parse_status": PARSE_UNSUPPORTED_SUFFIX,
            "text_length": 0,
            "csv_text_length": 50,
            "parsed_to_csv_length_ratio": None,
            "citation_level": "none",
            "visual_backend": None,
            "page_text_backend": None,
            "page_citation_available": False,
            "error_reason": "unsupported suffix: .pdf",
        },
    ]

    summary = summarize_records(records)

    assert summary["row_count"] == 2
    assert summary["suffix_counts"] == {".hwp": 1, ".pdf": 1}
    assert summary["parse_status_counts"] == {
        PARSE_PARSED: 1,
        PARSE_UNSUPPORTED_SUFFIX: 1,
    }
    assert summary["parser_backend_counts"] == {"hwp5txt": 1}
    assert summary["parsed_success_rate"] == 0.5
    assert summary["empty_parse_count"] == 0
    assert summary["text_length"]["median"] == 50
    assert summary["csv_text_length"]["median"] == 65
    assert summary["parsed_to_csv_length_ratio"]["median"] == 1.25
    assert summary["page_citation_available_count"] == 1
    assert summary["page_citation_coverage"] == 0.5
    assert summary["citation_level_counts"] == {"page": 1, "none": 1}
    assert summary["visual_backend_counts"] == {"libreoffice_pdf": 1}
    assert summary["page_text_backend_counts"] == {"pymupdf": 1}
    assert summary["top_error_reasons"] == {"unsupported suffix: .pdf": 1}


def test_summarize_records_counts_empty_suffix_and_limits_top_errors() -> None:
    records = [
        {
            "source_suffix": "" if idx == 0 else ".hwp",
            "parser_backend": None,
            "parse_status": PARSE_PARSER_ERROR,
            "text_length": 0,
            "csv_text_length": 10,
            "parsed_to_csv_length_ratio": None,
            "error_reason": f"error-{idx:02d}",
        }
        for idx in range(12)
    ]

    summary = summarize_records(records)

    assert summary["suffix_counts"] == {"": 1, ".hwp": 11}
    assert summary["top_error_reasons"] == {f"error-{idx:02d}": 1 for idx in range(10)}


def test_write_parse_artifacts_writes_manifest_and_summary(tmp_path: Path) -> None:
    records = [
        {
            "doc_id": "doc:000",
            "csv_row_id": "000",
            "source_path": "/tmp/sample.hwp",
            "source_suffix": ".hwp",
            "parser_backend": "hwp5txt",
            "parse_status": PARSE_PARSED,
            "text_path": "/tmp/parsed/text/doc_000.txt",
            "text_length": 100,
            "stderr_length": 0,
            "stderr_sample": "",
            "error_reason": None,
            "csv_text_length": 80,
            "parsed_to_csv_length_ratio": 1.25,
        },
        {
            "doc_id": "doc:001",
            "csv_row_id": "001",
            "source_path": "/tmp/sample.pdf",
            "source_suffix": ".pdf",
            "parser_backend": None,
            "parse_status": PARSE_UNSUPPORTED_SUFFIX,
            "text_path": None,
            "text_length": 0,
            "stderr_length": 0,
            "stderr_sample": "",
            "error_reason": "unsupported suffix: .pdf",
            "csv_text_length": 50,
            "parsed_to_csv_length_ratio": None,
        },
    ]

    summary = write_parse_artifacts(records, tmp_path)

    manifest_rows = [
        json.loads(line)
        for line in (tmp_path / "manifest.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    summary_json = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert manifest_rows == records
    assert summary_json == summary
