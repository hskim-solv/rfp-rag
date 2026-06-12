from __future__ import annotations

import json
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


@dataclass(frozen=True)
class ParseResult:
    status: str
    parser_backend: str | None
    text: str
    stderr: str
    error_reason: str | None


Runner = Callable[..., subprocess.CompletedProcess[Any]]


def safe_doc_filename(doc_id: str) -> str:
    return f"{doc_id.replace(':', '_')}.txt"


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _normalize_text(value: Any) -> str:
    return _stringify(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def parse_hwp_file(path: Path | str, timeout_seconds: int = 60, runner: Runner = subprocess.run) -> ParseResult:
    source = Path(path)
    cmd = [HWP5TXT_BACKEND, str(source)]
    try:
        completed = runner(cmd, capture_output=True, text=True, timeout=timeout_seconds, check=False)
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


def parse_document_source(doc: CorpusDocument, timeout_seconds: int = 60) -> ParseResult:
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
        return parse_hwp_file(source, timeout_seconds=timeout_seconds)
    return ParseResult(
        status=PARSE_UNSUPPORTED_SUFFIX,
        parser_backend=None,
        text="",
        stderr="",
        error_reason=f"unsupported suffix: {suffix or '<none>'}",
    )


def build_parse_record(doc: CorpusDocument, result: ParseResult, out_dir: Path | str) -> dict[str, Any]:
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
    }


def _count_nonempty(values: Iterable[Any]) -> dict[Any, int]:
    return dict(Counter(value for value in values if value))


def _count_present(values: Iterable[Any]) -> dict[Any, int]:
    return dict(Counter(value for value in values if value is not None))


def _distribution(values: Iterable[int | float | None]) -> dict[str, int | float | None]:
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
    parse_status_counts = Counter(row.get("parse_status") for row in rows if row.get("parse_status"))
    error_reason_counts = Counter(row.get("error_reason") for row in rows if row.get("error_reason"))
    parsed_count = parse_status_counts.get(PARSE_PARSED, 0)

    return {
        "row_count": row_count,
        "suffix_counts": _count_present(row.get("source_suffix") for row in rows),
        "parse_status_counts": dict(parse_status_counts),
        "parser_backend_counts": _count_nonempty(row.get("parser_backend") for row in rows),
        "parsed_success_rate": parsed_count / row_count if row_count else 0.0,
        "empty_parse_count": parse_status_counts.get(PARSE_EMPTY_TEXT, 0),
        "text_length": _distribution(row.get("text_length") for row in rows),
        "csv_text_length": _distribution(row.get("csv_text_length") for row in rows),
        "parsed_to_csv_length_ratio": _distribution(row.get("parsed_to_csv_length_ratio") for row in rows),
        "top_error_reasons": dict(error_reason_counts.most_common(10)),
    }


def write_parse_artifacts(records: Iterable[dict[str, Any]], out_dir: Path | str) -> dict[str, Any]:
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
