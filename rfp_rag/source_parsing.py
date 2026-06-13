from __future__ import annotations

import importlib
import json
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Callable, Iterable

from rfp_rag.corpus import CorpusDocument

PARSE_PARSED = "parsed"
PARSE_EMPTY_TEXT = "empty_text"
PARSE_UNSUPPORTED_SUFFIX = "unsupported_suffix"
PARSE_MISSING_SOURCE_FILE = "missing_source_file"
PARSE_PARSER_ERROR = "parser_error"
PARSE_TIMEOUT = "timeout"

HWP5TXT_BACKEND = "hwp5txt"
UNHWP_BACKEND = "unhwp"
LIBREOFFICE_PDF_BACKEND = "libreoffice_pdf"
PYMUPDF_BACKEND = "pymupdf"
CONVERTED_PDF_TEXT_BACKEND = "converted_pdf_pymupdf"
CSV_TEXT_DEGRADED_BACKEND = "csv_text_degraded"


@dataclass(frozen=True)
class ParseResult:
    status: str
    parser_backend: str | None
    text: str
    stderr: str
    error_reason: str | None
    attempts: list[dict[str, Any]] | None = None
    content_source: str | None = None
    source_quality: str | None = None


Runner = Callable[..., subprocess.CompletedProcess[Any]]
ExecutableFinder = Callable[..., str | None]
PdfPageTextExtractor = Callable[[Path], list[tuple[int, str]]]


def safe_doc_filename(doc_id: str) -> str:
    return f"{doc_id.replace(':', '_')}.txt"


def safe_doc_stem(doc_id: str) -> str:
    return doc_id.replace(":", "_")


def page_text_filename(doc_id: str) -> str:
    return f"{safe_doc_stem(doc_id)}.jsonl"


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _normalize_text(value: Any) -> str:
    return _stringify(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def _find_executable(
    name: str, *, extra_candidates: Iterable[Path | str] = ()
) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for candidate in extra_candidates:
        path = Path(candidate).expanduser()
        if path.is_file():
            return str(path)
    return None


def parse_hwp_file(
    path: Path | str, timeout_seconds: int = 60, runner: Runner = subprocess.run
) -> ParseResult:
    source = Path(path)
    cmd = [HWP5TXT_BACKEND, str(source)]
    try:
        completed = runner(
            cmd, capture_output=True, text=True, timeout=timeout_seconds, check=False
        )
    except subprocess.TimeoutExpired as exc:
        return ParseResult(
            status=PARSE_TIMEOUT,
            parser_backend=HWP5TXT_BACKEND,
            text=_normalize_text(exc.stdout),
            stderr=_stringify(exc.stderr),
            error_reason=f"parser timeout after {timeout_seconds}s",
        )
    except FileNotFoundError:
        return ParseResult(
            status=PARSE_PARSER_ERROR,
            parser_backend=HWP5TXT_BACKEND,
            text="",
            stderr="",
            error_reason=f"{HWP5TXT_BACKEND} not found",
        )
    except OSError as exc:
        return ParseResult(
            status=PARSE_PARSER_ERROR,
            parser_backend=HWP5TXT_BACKEND,
            text="",
            stderr="",
            error_reason=str(exc),
        )

    text = _normalize_text(completed.stdout)
    stderr = _stringify(completed.stderr)
    if completed.returncode != 0:
        return ParseResult(
            status=PARSE_PARSER_ERROR,
            parser_backend=HWP5TXT_BACKEND,
            text=text,
            stderr=stderr,
            error_reason=f"{HWP5TXT_BACKEND} exited {completed.returncode}",
        )
    if not text:
        return ParseResult(
            status=PARSE_EMPTY_TEXT,
            parser_backend=HWP5TXT_BACKEND,
            text="",
            stderr=stderr,
            error_reason="empty stdout",
        )
    return ParseResult(
        status=PARSE_PARSED,
        parser_backend=HWP5TXT_BACKEND,
        text=text,
        stderr=stderr,
        error_reason=None,
    )


def _parse_unhwp_file(
    path: Path | str,
    *,
    timeout_seconds: int = 60,
    runner: Runner = subprocess.run,
    executable_finder: ExecutableFinder = _find_executable,
) -> ParseResult:
    source = Path(path)
    executable = executable_finder(
        UNHWP_BACKEND, extra_candidates=["~/.cargo/bin/unhwp"]
    )
    if executable is None:
        return ParseResult(
            status=PARSE_PARSER_ERROR,
            parser_backend=UNHWP_BACKEND,
            text="",
            stderr="",
            error_reason=f"{UNHWP_BACKEND} not found",
        )

    cmd = [executable, "text", str(source)]
    try:
        completed = runner(
            cmd, capture_output=True, text=True, timeout=timeout_seconds, check=False
        )
    except subprocess.TimeoutExpired as exc:
        return ParseResult(
            status=PARSE_TIMEOUT,
            parser_backend=UNHWP_BACKEND,
            text=_normalize_text(exc.stdout),
            stderr=_stringify(exc.stderr),
            error_reason=f"{UNHWP_BACKEND} timeout after {timeout_seconds}s",
        )
    except OSError as exc:
        return ParseResult(
            status=PARSE_PARSER_ERROR,
            parser_backend=UNHWP_BACKEND,
            text="",
            stderr="",
            error_reason=str(exc),
        )

    text = _normalize_text(completed.stdout)
    stderr = _stringify(completed.stderr)
    if completed.returncode != 0:
        return ParseResult(
            status=PARSE_PARSER_ERROR,
            parser_backend=UNHWP_BACKEND,
            text=text,
            stderr=stderr,
            error_reason=f"{UNHWP_BACKEND} exited {completed.returncode}",
        )
    if not text:
        return ParseResult(
            status=PARSE_EMPTY_TEXT,
            parser_backend=UNHWP_BACKEND,
            text="",
            stderr=stderr,
            error_reason="empty stdout",
        )
    return ParseResult(
        status=PARSE_PARSED,
        parser_backend=UNHWP_BACKEND,
        text=text,
        stderr=stderr,
        error_reason=None,
    )


def _attempt_record(result: ParseResult) -> dict[str, Any]:
    return {
        "backend": result.parser_backend,
        "status": result.status,
        "text_length": len(result.text),
        "error_reason": result.error_reason,
    }


def _with_fallback_metadata(
    result: ParseResult,
    *,
    attempts: list[dict[str, Any]],
    content_source: str | None = None,
    source_quality: str | None = None,
) -> ParseResult:
    return ParseResult(
        status=result.status,
        parser_backend=result.parser_backend,
        text=result.text,
        stderr=result.stderr,
        error_reason=result.error_reason,
        attempts=attempts,
        content_source=content_source
        if content_source is not None
        else result.content_source,
        source_quality=source_quality
        if source_quality is not None
        else result.source_quality,
    )


def _parse_converted_pdf_text_file(
    path: Path | str,
    *,
    doc_id: str,
    out_dir: Path | str | None,
    timeout_seconds: int = 60,
    runner: Runner = subprocess.run,
    executable_finder: ExecutableFinder = _find_executable,
    pdf_page_text_extractor: PdfPageTextExtractor | None = None,
) -> ParseResult:
    if out_dir is None:
        return ParseResult(
            status=PARSE_PARSER_ERROR,
            parser_backend=CONVERTED_PDF_TEXT_BACKEND,
            text="",
            stderr="",
            error_reason="converted pdf fallback requires out_dir",
        )

    pdf_path, conversion_error = _convert_hwp_to_pdf(
        Path(path),
        doc_id,
        Path(out_dir),
        timeout_seconds=timeout_seconds,
        runner=runner,
        executable_finder=executable_finder,
    )
    if pdf_path is None:
        return ParseResult(
            status=PARSE_PARSER_ERROR,
            parser_backend=CONVERTED_PDF_TEXT_BACKEND,
            text="",
            stderr="",
            error_reason=conversion_error,
        )

    try:
        extractor = pdf_page_text_extractor or _extract_pdf_pages_with_pymupdf
        pages = extractor(pdf_path)
    except ImportError:
        return ParseResult(
            status=PARSE_PARSER_ERROR,
            parser_backend=CONVERTED_PDF_TEXT_BACKEND,
            text="",
            stderr="",
            error_reason="pymupdf not installed",
        )
    except Exception as exc:
        return ParseResult(
            status=PARSE_PARSER_ERROR,
            parser_backend=CONVERTED_PDF_TEXT_BACKEND,
            text="",
            stderr="",
            error_reason=str(exc),
        )

    text = "\n".join(
        text
        for _, text in (
            (_page, _normalize_text(page_text)) for _page, page_text in pages
        )
        if text
    )
    if not text:
        return ParseResult(
            status=PARSE_EMPTY_TEXT,
            parser_backend=CONVERTED_PDF_TEXT_BACKEND,
            text="",
            stderr="",
            error_reason="empty pdf page text",
        )
    return ParseResult(
        status=PARSE_PARSED,
        parser_backend=CONVERTED_PDF_TEXT_BACKEND,
        text=text,
        stderr="",
        error_reason=None,
        content_source="converted_pdf_text",
        source_quality="source_converted_pdf",
    )


def parse_hwp_file_with_fallbacks(
    path: Path | str,
    *,
    doc_id: str,
    csv_text: str = "",
    out_dir: Path | str | None = None,
    timeout_seconds: int = 60,
    runner: Runner = subprocess.run,
    executable_finder: ExecutableFinder = _find_executable,
    pdf_page_text_extractor: PdfPageTextExtractor | None = None,
) -> ParseResult:
    attempts: list[dict[str, Any]] = []

    result = _parse_unhwp_file(
        path,
        timeout_seconds=timeout_seconds,
        runner=runner,
        executable_finder=executable_finder,
    )
    attempts.append(_attempt_record(result))
    if result.status == PARSE_PARSED and result.text:
        return _with_fallback_metadata(
            result,
            attempts=attempts,
            content_source="source_hwp_text",
            source_quality="source_parsed",
        )

    result = parse_hwp_file(path, timeout_seconds=timeout_seconds, runner=runner)
    attempts.append(_attempt_record(result))
    if result.status == PARSE_PARSED and result.text:
        return _with_fallback_metadata(
            result,
            attempts=attempts,
            content_source="source_hwp_text",
            source_quality="source_parsed",
        )

    result = _parse_converted_pdf_text_file(
        path,
        doc_id=doc_id,
        out_dir=out_dir,
        timeout_seconds=timeout_seconds,
        runner=runner,
        executable_finder=executable_finder,
        pdf_page_text_extractor=pdf_page_text_extractor,
    )
    attempts.append(_attempt_record(result))
    if result.status == PARSE_PARSED and result.text:
        return _with_fallback_metadata(
            result,
            attempts=attempts,
            content_source="converted_pdf_text",
            source_quality="source_converted_pdf",
        )

    csv_fallback_text = _normalize_text(csv_text)
    if csv_fallback_text:
        csv_result = ParseResult(
            status=PARSE_PARSED,
            parser_backend=CSV_TEXT_DEGRADED_BACKEND,
            text=csv_fallback_text,
            stderr="",
            error_reason=None,
        )
        attempts.append(_attempt_record(csv_result))
        return _with_fallback_metadata(
            csv_result,
            attempts=attempts,
            content_source="csv_text_fallback",
            source_quality="degraded_csv_text",
        )

    return _with_fallback_metadata(result, attempts=attempts)


def parse_document_source(
    doc: CorpusDocument,
    timeout_seconds: int = 60,
    *,
    out_dir: Path | str | None = None,
    runner: Runner = subprocess.run,
    executable_finder: ExecutableFinder = _find_executable,
    pdf_page_text_extractor: PdfPageTextExtractor | None = None,
) -> ParseResult:
    source_path = doc.metadata.get("resolved_filesystem_path")
    if not source_path:
        return ParseResult(
            status=PARSE_MISSING_SOURCE_FILE,
            parser_backend=None,
            text="",
            stderr="",
            error_reason="missing source file",
        )

    source = Path(str(source_path))
    if not source.is_file():
        return ParseResult(
            status=PARSE_MISSING_SOURCE_FILE,
            parser_backend=None,
            text="",
            stderr="",
            error_reason="missing source file",
        )

    suffix = source.suffix.lower()
    if suffix == ".hwp":
        return parse_hwp_file_with_fallbacks(
            source,
            doc_id=doc.doc_id,
            csv_text=doc.text,
            out_dir=out_dir,
            timeout_seconds=timeout_seconds,
            runner=runner,
            executable_finder=executable_finder,
            pdf_page_text_extractor=pdf_page_text_extractor,
        )
    return ParseResult(
        status=PARSE_UNSUPPORTED_SUFFIX,
        parser_backend=None,
        text="",
        stderr="",
        error_reason=f"unsupported suffix: {suffix or '<none>'}",
    )


def _extract_pdf_pages_with_pymupdf(pdf_path: Path) -> list[tuple[int, str]]:
    pymupdf = importlib.import_module("pymupdf")
    pages: list[tuple[int, str]] = []
    with pymupdf.open(str(pdf_path)) as document:
        for index, page in enumerate(document, start=1):
            text = _normalize_text(page.get_text("text"))
            if text:
                pages.append((index, text))
    return pages


def _write_page_text_artifact(
    doc_id: str, pages: list[tuple[int, str]], out_dir: Path
) -> str | None:
    if not pages:
        return None
    page_text_dir = out_dir / "page_text"
    page_text_dir.mkdir(parents=True, exist_ok=True)
    target = page_text_dir / page_text_filename(doc_id)
    with target.open("w", encoding="utf-8") as f:
        for page_number, text in pages:
            f.write(
                json.dumps(
                    {"page": page_number, "text": text},
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
    return str(target)


def _copy_pdf_source_for_citation(source: Path, doc_id: str, out_dir: Path) -> Path:
    pdf_dir = out_dir / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    target = pdf_dir / f"{safe_doc_stem(doc_id)}.pdf"
    if source.resolve() != target.resolve():
        target.write_bytes(source.read_bytes())
    return target


def _convert_hwp_to_pdf(
    source: Path,
    doc_id: str,
    out_dir: Path,
    *,
    timeout_seconds: int,
    runner: Runner,
    executable_finder: ExecutableFinder,
) -> tuple[Path | None, str | None]:
    soffice = executable_finder(
        "soffice",
        extra_candidates=[
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            "/Applications/LibreOffice.app/Contents/MacOS/libreoffice",
        ],
    )
    if soffice is None:
        return None, "soffice not found"

    pdf_dir = out_dir / "pdf"
    work_dir = out_dir / "pdf_work" / safe_doc_stem(doc_id)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        completed = runner(
            [
                soffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(work_dir),
                str(source),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, f"pdf conversion timeout after {timeout_seconds}s"
    except OSError as exc:
        return None, str(exc)

    if completed.returncode != 0:
        return None, f"soffice exited {completed.returncode}"
    converted = work_dir / f"{source.stem}.pdf"
    if not converted.is_file():
        return None, "converted pdf not found"
    target = pdf_dir / f"{safe_doc_stem(doc_id)}.pdf"
    converted.replace(target)
    return target, None


def _build_page_citation_evidence(
    doc: CorpusDocument,
    out_dir: Path,
    *,
    timeout_seconds: int,
    runner: Runner,
    executable_finder: ExecutableFinder,
    pdf_page_text_extractor: PdfPageTextExtractor,
) -> dict[str, Any]:
    source_path = doc.metadata.get("resolved_filesystem_path")
    if not source_path:
        return {
            "converted_pdf_path": None,
            "visual_backend": None,
            "page_text_backend": None,
            "page_text_path": None,
            "page_count": 0,
            "page_citation_available": False,
            "page_citation_error_reason": "missing source file",
        }

    source = Path(str(source_path))
    suffix = source.suffix.lower()
    pdf_path: Path | None = None
    visual_backend: str | None = None
    conversion_error: str | None = None
    if suffix == ".hwp":
        pdf_path, conversion_error = _convert_hwp_to_pdf(
            source,
            doc.doc_id,
            out_dir,
            timeout_seconds=timeout_seconds,
            runner=runner,
            executable_finder=executable_finder,
        )
        visual_backend = LIBREOFFICE_PDF_BACKEND if pdf_path is not None else None
    elif suffix == ".pdf":
        pdf_path = _copy_pdf_source_for_citation(source, doc.doc_id, out_dir)
        visual_backend = "source_pdf"
    else:
        conversion_error = f"unsupported citation suffix: {suffix or '<none>'}"

    if pdf_path is None:
        return {
            "converted_pdf_path": None,
            "visual_backend": visual_backend,
            "page_text_backend": None,
            "page_text_path": None,
            "page_count": 0,
            "page_citation_available": False,
            "page_citation_error_reason": conversion_error,
        }

    try:
        pages = pdf_page_text_extractor(pdf_path)
    except ImportError:
        return {
            "converted_pdf_path": str(pdf_path),
            "visual_backend": visual_backend,
            "page_text_backend": None,
            "page_text_path": None,
            "page_count": 0,
            "page_citation_available": False,
            "page_citation_error_reason": "pymupdf not installed",
        }
    except Exception as exc:
        return {
            "converted_pdf_path": str(pdf_path),
            "visual_backend": visual_backend,
            "page_text_backend": None,
            "page_text_path": None,
            "page_count": 0,
            "page_citation_available": False,
            "page_citation_error_reason": str(exc),
        }

    page_text_path = _write_page_text_artifact(doc.doc_id, pages, out_dir)
    return {
        "converted_pdf_path": str(pdf_path),
        "visual_backend": visual_backend,
        "page_text_backend": PYMUPDF_BACKEND if page_text_path is not None else None,
        "page_text_path": page_text_path,
        "page_count": len(pages),
        "page_citation_available": page_text_path is not None,
        "page_citation_error_reason": None
        if page_text_path is not None
        else "empty pdf page text",
    }


def _content_source_for(doc: CorpusDocument, result: ParseResult) -> str | None:
    if result.status != PARSE_PARSED:
        return None
    source_path = doc.metadata.get("resolved_filesystem_path")
    suffix = Path(str(source_path)).suffix.lower() if source_path else ""
    if suffix == ".hwp":
        return "source_hwp_text"
    if suffix == ".pdf":
        return "source_pdf_text"
    return "source_text"


def build_parse_record(
    doc: CorpusDocument,
    result: ParseResult,
    out_dir: Path | str,
    *,
    enable_page_citation: bool = False,
    citation_timeout_seconds: int = 60,
    citation_runner: Runner = subprocess.run,
    executable_finder: ExecutableFinder = _find_executable,
    pdf_page_text_extractor: PdfPageTextExtractor = _extract_pdf_pages_with_pymupdf,
) -> dict[str, Any]:
    """Build a parse manifest row and persist parsed text for successful results."""
    out = Path(out_dir)
    source_path = doc.metadata.get("resolved_filesystem_path")
    source_path_text = None if source_path is None else str(source_path)
    source_suffix = Path(source_path_text).suffix.lower() if source_path_text else ""
    text_path: str | None = None

    if result.status == PARSE_PARSED:
        parsed_text_dir = out / "text"
        parsed_text_dir.mkdir(parents=True, exist_ok=True)
        target = parsed_text_dir / safe_doc_filename(doc.doc_id)
        text_with_trailing_newline = result.text.rstrip("\n") + "\n"
        target.write_text(text_with_trailing_newline, encoding="utf-8")
        text_path = str(target)

    text_length = len(result.text)
    csv_text_length = len(doc.text or "")
    ratio = text_length / csv_text_length if text_length and csv_text_length else None
    content_source = (
        result.content_source
        if result.content_source is not None
        else _content_source_for(doc, result)
    )
    source_quality = (
        result.source_quality
        if result.source_quality is not None
        else "source_parsed"
        if result.status == PARSE_PARSED
        else "source_unparsed"
    )
    citation_evidence = (
        _build_page_citation_evidence(
            doc,
            out,
            timeout_seconds=citation_timeout_seconds,
            runner=citation_runner,
            executable_finder=executable_finder,
            pdf_page_text_extractor=pdf_page_text_extractor,
        )
        if enable_page_citation
        else {
            "converted_pdf_path": None,
            "visual_backend": None,
            "page_text_backend": None,
            "page_text_path": None,
            "page_count": 0,
            "page_citation_available": False,
            "page_citation_error_reason": None,
        }
    )
    citation_level = (
        "page"
        if citation_evidence["page_citation_available"]
        else "document"
        if result.status == PARSE_PARSED
        else "none"
    )

    return {
        "doc_id": doc.doc_id,
        "csv_row_id": doc.csv_row_id,
        "source_path": source_path_text,
        "source_suffix": source_suffix,
        "parser_backend": result.parser_backend,
        "parse_status": result.status,
        "text_path": text_path,
        "text_length": text_length,
        "stderr_length": len(result.stderr),
        "stderr_sample": result.stderr[:500],
        "error_reason": result.error_reason,
        "csv_text_length": csv_text_length,
        "parsed_to_csv_length_ratio": ratio,
        "content_source": content_source,
        "source_quality": source_quality,
        "text_backend_attempts": result.attempts or [],
        "citation_level": citation_level,
        **citation_evidence,
    }


def _count_nonempty(values: Iterable[Any]) -> dict[Any, int]:
    return dict(Counter(value for value in values if value))


def _count_present(values: Iterable[Any]) -> dict[Any, int]:
    return dict(Counter(value for value in values if value is not None))


def _distribution(
    values: Iterable[int | float | None],
) -> dict[str, int | float | None]:
    numeric_values = [value for value in values if value is not None]
    if not numeric_values:
        return {"min": None, "median": None, "max": None}
    return {
        "min": min(numeric_values),
        "median": median(numeric_values),
        "max": max(numeric_values),
    }


def summarize_records(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    row_count = len(rows)
    parse_status_counts = Counter(
        row.get("parse_status") for row in rows if row.get("parse_status")
    )
    error_reason_counts = Counter(
        row.get("error_reason") for row in rows if row.get("error_reason")
    )
    parsed_count = parse_status_counts.get(PARSE_PARSED, 0)
    page_citation_available_count = sum(
        1 for row in rows if row.get("page_citation_available") is True
    )

    return {
        "row_count": row_count,
        "suffix_counts": _count_present(row.get("source_suffix") for row in rows),
        "parse_status_counts": dict(parse_status_counts),
        "parser_backend_counts": _count_nonempty(
            row.get("parser_backend") for row in rows
        ),
        "content_source_counts": _count_nonempty(
            row.get("content_source") for row in rows
        ),
        "source_quality_counts": _count_nonempty(
            row.get("source_quality") for row in rows
        ),
        "visual_backend_counts": _count_nonempty(
            row.get("visual_backend") for row in rows
        ),
        "page_text_backend_counts": _count_nonempty(
            row.get("page_text_backend") for row in rows
        ),
        "citation_level_counts": _count_nonempty(
            row.get("citation_level") for row in rows
        ),
        "parsed_success_rate": parsed_count / row_count if row_count else 0.0,
        "page_citation_available_count": page_citation_available_count,
        "page_citation_coverage": page_citation_available_count / row_count
        if row_count
        else 0.0,
        "degraded_csv_fallback_count": sum(
            1 for row in rows if row.get("parser_backend") == CSV_TEXT_DEGRADED_BACKEND
        ),
        "empty_parse_count": parse_status_counts.get(PARSE_EMPTY_TEXT, 0),
        "text_length": _distribution(row.get("text_length") for row in rows),
        "csv_text_length": _distribution(row.get("csv_text_length") for row in rows),
        "parsed_to_csv_length_ratio": _distribution(
            row.get("parsed_to_csv_length_ratio") for row in rows
        ),
        "top_error_reasons": dict(error_reason_counts.most_common(10)),
    }


def write_parse_artifacts(
    records: Iterable[dict[str, Any]], out_dir: Path | str
) -> dict[str, Any]:
    rows = list(records)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    manifest_path = out / "manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    summary = summarize_records(rows)
    summary_path = out / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
