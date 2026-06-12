from __future__ import annotations

import subprocess
from pathlib import Path

from rfp_rag.corpus import CorpusDocument
from rfp_rag.source_parsing import (
    PARSE_EMPTY_TEXT,
    PARSE_PARSED,
    PARSE_PARSER_ERROR,
    PARSE_TIMEOUT,
    PARSE_UNSUPPORTED_SUFFIX,
    ParseResult,
    build_parse_record,
    parse_hwp_file,
    safe_doc_filename,
    summarize_records,
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
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="  본문\n", stderr="warning")

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
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=" \n ", stderr="")

    result = parse_hwp_file(source, timeout_seconds=5, runner=runner)

    assert result.status == PARSE_EMPTY_TEXT
    assert result.text == ""
    assert result.error_reason == "empty stdout"


def test_parse_hwp_file_nonzero_exit_is_parser_error(tmp_path: Path) -> None:
    source = tmp_path / "sample.hwp"
    source.write_bytes(b"fake")

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=2, stdout="", stderr="boom")

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
    assert record["parsed_to_csv_length_ratio"] == len("원문 본문입니다") / len("CSV 본문입니다")
    assert record["stderr_length"] == len("diagnostic")
    assert record["stderr_sample"] == "diagnostic"
    assert record["text_path"] == str(out_dir / "text" / safe_doc_filename("doc:000"))
    assert Path(record["text_path"]).read_text(encoding="utf-8") == "원문 본문입니다\n"


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
            "error_reason": None,
        },
        {
            "source_suffix": ".pdf",
            "parser_backend": None,
            "parse_status": PARSE_UNSUPPORTED_SUFFIX,
            "text_length": 0,
            "csv_text_length": 50,
            "parsed_to_csv_length_ratio": None,
            "error_reason": "unsupported suffix: .pdf",
        },
    ]

    summary = summarize_records(records)

    assert summary["row_count"] == 2
    assert summary["suffix_counts"] == {".hwp": 1, ".pdf": 1}
    assert summary["parse_status_counts"] == {PARSE_PARSED: 1, PARSE_UNSUPPORTED_SUFFIX: 1}
    assert summary["parser_backend_counts"] == {"hwp5txt": 1}
    assert summary["parsed_success_rate"] == 0.5
    assert summary["empty_parse_count"] == 0
    assert summary["text_length"]["median"] == 50
    assert summary["csv_text_length"]["median"] == 65
    assert summary["parsed_to_csv_length_ratio"]["median"] == 1.25
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
