from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any, Callable, Iterable

from .corpus import CorpusDocument

BAKEOFF_OK = "ok"
BAKEOFF_MISSING_DEPENDENCY = "missing_dependency"
BAKEOFF_UNSUPPORTED_FORMAT = "unsupported_format"
BAKEOFF_EMPTY_OUTPUT = "empty_output"
BAKEOFF_TIMEOUT = "timeout"
BAKEOFF_BACKEND_ERROR = "backend_error"

Runner = Callable[..., subprocess.CompletedProcess[Any]]


@dataclass(frozen=True)
class BakeoffSample:
    doc_id: str
    csv_row_id: str
    source_path: str
    source_suffix: str
    project_name: str
    issuer: str
    csv_text_length: int
    prior_parse_status: str | None
    prior_text_length: int | None
    prior_ratio: float | None
    selection_reasons: list[str]


@dataclass(frozen=True)
class BakeoffResult:
    doc_id: str
    source_path: str
    source_suffix: str
    backend: str
    status: str
    elapsed_ms: int
    text_path: str | None
    markdown_path: str | None
    html_path: str | None
    json_path: str | None
    rendered_pdf_path: str | None
    rendered_svg_count: int
    rendered_png_count: int
    asset_count: int
    text_length: int
    markdown_length: int
    html_length: int
    json_length: int
    table_count: int
    image_count: int
    page_count: int | None
    stdout_length: int
    stderr_length: int
    error_reason: str | None


def load_parse_manifest(path: Path | str) -> list[dict[str, Any]]:
    manifest_path = Path(path)
    return [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _manifest_by_doc_id(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["doc_id"]): row for row in rows}


def _sample_from_doc(
    doc: CorpusDocument,
    manifest_row: dict[str, Any] | None,
    reasons: set[str],
) -> BakeoffSample:
    source_path = str(doc.metadata.get("resolved_filesystem_path") or "")
    suffix = Path(source_path).suffix.lower() if source_path else ""
    return BakeoffSample(
        doc_id=doc.doc_id,
        csv_row_id=doc.csv_row_id,
        source_path=source_path,
        source_suffix=suffix,
        project_name=str(doc.metadata.get("project_name") or ""),
        issuer=str(doc.metadata.get("issuer") or ""),
        csv_text_length=len(doc.text or ""),
        prior_parse_status=None if manifest_row is None else str(manifest_row.get("parse_status") or ""),
        prior_text_length=None if manifest_row is None else int(manifest_row.get("text_length") or 0),
        prior_ratio=None if manifest_row is None else manifest_row.get("parsed_to_csv_length_ratio"),
        selection_reasons=sorted(reasons),
    )


def select_bakeoff_samples(
    docs: Iterable[CorpusDocument],
    manifest_rows: Iterable[dict[str, Any]],
    *,
    hwp_limit: int = 12,
    include_pdfs: bool = True,
) -> list[BakeoffSample]:
    doc_list = list(docs)
    manifest = _manifest_by_doc_id(manifest_rows)
    reasons_by_doc: dict[str, set[str]] = defaultdict(set)

    hwp_docs = [
        doc
        for doc in doc_list
        if str(doc.metadata.get("resolved_filesystem_path") or "").lower().endswith(".hwp")
    ]
    pdf_docs = [
        doc
        for doc in doc_list
        if str(doc.metadata.get("resolved_filesystem_path") or "").lower().endswith(".pdf")
    ]

    for doc in hwp_docs:
        row = manifest.get(doc.doc_id, {})
        if row.get("parse_status") in {"empty_text", "parser_error"}:
            reasons_by_doc[doc.doc_id].add(str(row.get("parse_status")))

    for doc in sorted(
        hwp_docs,
        key=lambda item: int(manifest.get(item.doc_id, {}).get("text_length") or 0),
        reverse=True,
    )[:4]:
        reasons_by_doc[doc.doc_id].add("large_text")

    ratio_docs = [
        doc
        for doc in hwp_docs
        if manifest.get(doc.doc_id, {}).get("parsed_to_csv_length_ratio") is not None
    ]
    for doc in sorted(
        ratio_docs,
        key=lambda item: float(manifest[item.doc_id]["parsed_to_csv_length_ratio"]),
        reverse=True,
    )[:4]:
        reasons_by_doc[doc.doc_id].add("high_ratio")

    parsed_hwp_docs = [doc for doc in hwp_docs if manifest.get(doc.doc_id, {}).get("parse_status") == "parsed"]
    parsed_hwp_docs = sorted(
        parsed_hwp_docs,
        key=lambda item: int(manifest.get(item.doc_id, {}).get("text_length") or 0),
    )
    if parsed_hwp_docs:
        mid = len(parsed_hwp_docs) // 2
        for doc in parsed_hwp_docs[max(0, mid - 2) : mid + 3]:
            reasons_by_doc[doc.doc_id].add("median_text")

    selected_hwp_ids = sorted(reasons_by_doc)
    if len(selected_hwp_ids) > hwp_limit:
        priority = {"empty_text": 0, "parser_error": 0, "large_text": 1, "high_ratio": 2, "median_text": 3}

        def rank(doc_id: str) -> tuple[int, str]:
            reasons = reasons_by_doc[doc_id]
            best = min(priority.get(reason, 9) for reason in reasons)
            return (best, doc_id)

        selected_hwp_ids = sorted(sorted(selected_hwp_ids, key=rank)[:hwp_limit])

    selected_docs = {doc.doc_id: doc for doc in hwp_docs}
    samples = [
        _sample_from_doc(selected_docs[doc_id], manifest.get(doc_id), reasons_by_doc[doc_id])
        for doc_id in selected_hwp_ids
    ]

    if include_pdfs:
        for doc in sorted(pdf_docs, key=lambda item: item.doc_id):
            samples.append(_sample_from_doc(doc, manifest.get(doc.doc_id), {"pdf_reference"}))

    return sorted(samples, key=lambda sample: sample.doc_id)


def _distribution(values: Iterable[int | float | None]) -> dict[str, int | float | None]:
    numbers = [value for value in values if value is not None]
    if not numbers:
        return {"min": None, "median": None, "max": None}
    return {"min": min(numbers), "median": median(numbers), "max": max(numbers)}


def _safe_doc_stem(doc_id: str) -> str:
    return doc_id.replace(":", "_")


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _normalize_output(value: Any) -> str:
    return _stringify(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def _empty_result(
    sample: BakeoffSample,
    *,
    backend: str,
    status: str,
    elapsed_ms: int = 0,
    stdout: Any = "",
    stderr: Any = "",
    error_reason: str | None,
) -> BakeoffResult:
    stdout_text = _stringify(stdout)
    stderr_text = _stringify(stderr)
    return BakeoffResult(
        doc_id=sample.doc_id,
        source_path=sample.source_path,
        source_suffix=sample.source_suffix,
        backend=backend,
        status=status,
        elapsed_ms=elapsed_ms,
        text_path=None,
        markdown_path=None,
        html_path=None,
        json_path=None,
        rendered_pdf_path=None,
        rendered_svg_count=0,
        rendered_png_count=0,
        asset_count=0,
        text_length=0,
        markdown_length=0,
        html_length=0,
        json_length=0,
        table_count=0,
        image_count=0,
        page_count=None,
        stdout_length=len(stdout_text),
        stderr_length=len(stderr_text),
        error_reason=error_reason,
    )


def run_command_backend(
    sample: BakeoffSample,
    *,
    backend: str,
    command: list[str],
    out_dir: Path | str,
    timeout_seconds: int,
    output_kind: str,
    runner: Runner = subprocess.run,
) -> BakeoffResult:
    started = time.perf_counter()
    try:
        completed = runner(command, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _empty_result(
            sample,
            backend=backend,
            status=BAKEOFF_TIMEOUT,
            elapsed_ms=elapsed_ms,
            stdout=exc.stdout or exc.output,
            stderr=exc.stderr,
            error_reason=f"backend timeout after {timeout_seconds}s",
        )
    except FileNotFoundError:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _empty_result(
            sample,
            backend=backend,
            status=BAKEOFF_MISSING_DEPENDENCY,
            elapsed_ms=elapsed_ms,
            error_reason=f"{command[0]} not found",
        )
    except OSError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _empty_result(
            sample,
            backend=backend,
            status=BAKEOFF_BACKEND_ERROR,
            elapsed_ms=elapsed_ms,
            error_reason=str(exc),
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    stdout = _normalize_output(completed.stdout)
    stderr = _stringify(completed.stderr)
    if completed.returncode != 0:
        return _empty_result(
            sample,
            backend=backend,
            status=BAKEOFF_BACKEND_ERROR,
            elapsed_ms=elapsed_ms,
            stdout=stdout,
            stderr=stderr,
            error_reason=f"{command[0]} exited {completed.returncode}",
        )
    if not stdout:
        return _empty_result(
            sample,
            backend=backend,
            status=BAKEOFF_EMPTY_OUTPUT,
            elapsed_ms=elapsed_ms,
            stdout=stdout,
            stderr=stderr,
            error_reason="empty output",
        )

    backend_dir = Path(out_dir) / "backends" / backend
    backend_dir.mkdir(parents=True, exist_ok=True)
    suffix_by_kind = {"text": ".txt", "markdown": ".md", "html": ".html", "json": ".json", "xml": ".xml"}
    extension = suffix_by_kind.get(output_kind, ".txt")
    output_path = backend_dir / f"{_safe_doc_stem(sample.doc_id)}{extension}"
    output_path.write_text(stdout.rstrip("\n") + "\n", encoding="utf-8")

    text_path = str(output_path) if output_kind in {"text", "xml"} else None
    markdown_path = str(output_path) if output_kind == "markdown" else None
    html_path = str(output_path) if output_kind == "html" else None
    json_path = str(output_path) if output_kind == "json" else None
    lowered_output = stdout.lower()

    return BakeoffResult(
        doc_id=sample.doc_id,
        source_path=sample.source_path,
        source_suffix=sample.source_suffix,
        backend=backend,
        status=BAKEOFF_OK,
        elapsed_ms=elapsed_ms,
        text_path=text_path,
        markdown_path=markdown_path,
        html_path=html_path,
        json_path=json_path,
        rendered_pdf_path=None,
        rendered_svg_count=0,
        rendered_png_count=0,
        asset_count=0,
        text_length=len(stdout) if output_kind in {"text", "xml"} else 0,
        markdown_length=len(stdout) if output_kind == "markdown" else 0,
        html_length=len(stdout) if output_kind == "html" else 0,
        json_length=len(stdout) if output_kind == "json" else 0,
        table_count=lowered_output.count("<table"),
        image_count=lowered_output.count("<img"),
        page_count=None,
        stdout_length=len(stdout),
        stderr_length=len(stderr),
        error_reason=None,
    )


def run_optional_import_backend(
    sample: BakeoffSample,
    *,
    backend: str,
    module_name: str,
    out_dir: Path | str,
) -> BakeoffResult:
    try:
        __import__(module_name)
    except ImportError:
        return _empty_result(
            sample,
            backend=backend,
            status=BAKEOFF_MISSING_DEPENDENCY,
            error_reason=f"{module_name} not installed",
        )

    return _empty_result(
        sample,
        backend=backend,
        status=BAKEOFF_BACKEND_ERROR,
        error_reason=f"{backend} installed but runner not implemented",
    )


def run_backend_for_sample(
    sample: BakeoffSample,
    *,
    backend: str,
    out_dir: Path | str,
    timeout_seconds: int = 60,
) -> BakeoffResult:
    suffix = sample.source_suffix.lower()
    if backend in {"hwp5txt", "hwp5html", "hwp5odt"} and suffix != ".hwp":
        return _empty_result(
            sample,
            backend=backend,
            status=BAKEOFF_UNSUPPORTED_FORMAT,
            error_reason=f"{backend} supports only .hwp",
        )
    if backend in {"rhwp", "unhwp", "hwpxkit"} and suffix not in {".hwp", ".hwpx"}:
        return _empty_result(
            sample,
            backend=backend,
            status=BAKEOFF_UNSUPPORTED_FORMAT,
            error_reason=f"{backend} supports only .hwp/.hwpx",
        )
    if backend == "libreoffice_pdf" and suffix != ".hwp":
        return _empty_result(
            sample,
            backend=backend,
            status=BAKEOFF_UNSUPPORTED_FORMAT,
            error_reason="libreoffice_pdf supports only .hwp",
        )

    if backend == "hwp5txt":
        return run_command_backend(
            sample,
            backend=backend,
            command=["hwp5txt", sample.source_path],
            out_dir=out_dir,
            timeout_seconds=timeout_seconds,
            output_kind="text",
        )
    if backend == "hwp5html":
        return run_command_backend(
            sample,
            backend=backend,
            command=["hwp5html", "--html", sample.source_path],
            out_dir=out_dir,
            timeout_seconds=timeout_seconds,
            output_kind="html",
        )
    if backend == "hwp5odt":
        return run_command_backend(
            sample,
            backend=backend,
            command=["hwp5odt", "--document", sample.source_path],
            out_dir=out_dir,
            timeout_seconds=timeout_seconds,
            output_kind="xml",
        )
    if backend == "rhwp":
        return run_optional_import_backend(sample, backend=backend, module_name="rhwp", out_dir=out_dir)
    if backend == "unhwp":
        if shutil.which("unhwp") is None:
            return _empty_result(
                sample,
                backend=backend,
                status=BAKEOFF_MISSING_DEPENDENCY,
                error_reason="unhwp not found",
            )
        return run_command_backend(
            sample,
            backend=backend,
            command=["unhwp", sample.source_path],
            out_dir=out_dir,
            timeout_seconds=timeout_seconds,
            output_kind="markdown",
        )
    if backend == "hwpxkit":
        return run_optional_import_backend(sample, backend=backend, module_name="hwpxkit", out_dir=out_dir)
    if backend == "libreoffice_pdf":
        if shutil.which("soffice") is None and shutil.which("libreoffice") is None:
            return _empty_result(
                sample,
                backend=backend,
                status=BAKEOFF_MISSING_DEPENDENCY,
                error_reason="soffice not found",
            )
        return _empty_result(
            sample,
            backend=backend,
            status=BAKEOFF_BACKEND_ERROR,
            error_reason="libreoffice_pdf runner not implemented in first bakeoff",
        )
    return _empty_result(
        sample,
        backend=backend,
        status=BAKEOFF_BACKEND_ERROR,
        error_reason=f"unknown backend: {backend}",
    )


def summarize_bakeoff_results(results: Iterable[BakeoffResult]) -> dict[str, Any]:
    rows = list(results)
    backend_counts = Counter(row.backend for row in rows)
    status_counts = Counter(row.status for row in rows)
    errors = Counter(row.error_reason for row in rows if row.error_reason)
    by_backend: dict[str, list[BakeoffResult]] = defaultdict(list)
    for row in rows:
        by_backend[row.backend].append(row)
    return {
        "result_count": len(rows),
        "backend_counts": dict(sorted(backend_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "backend_status_counts": {
            backend: dict(sorted(Counter(row.status for row in backend_rows).items()))
            for backend, backend_rows in sorted(by_backend.items())
        },
        "backend_success_rate": {
            backend: (sum(1 for row in backend_rows if row.status == BAKEOFF_OK) / len(backend_rows))
            for backend, backend_rows in sorted(by_backend.items())
        },
        "elapsed_ms_by_backend": {
            backend: _distribution(row.elapsed_ms for row in backend_rows)
            for backend, backend_rows in sorted(by_backend.items())
        },
        "text_length_by_backend": {
            backend: _distribution(row.text_length for row in backend_rows)
            for backend, backend_rows in sorted(by_backend.items())
        },
        "table_count_by_backend": {
            backend: _distribution(row.table_count for row in backend_rows)
            for backend, backend_rows in sorted(by_backend.items())
        },
        "image_count_by_backend": {
            backend: _distribution(row.image_count for row in backend_rows)
            for backend, backend_rows in sorted(by_backend.items())
        },
        "asset_count_by_backend": {
            backend: _distribution(row.asset_count for row in backend_rows)
            for backend, backend_rows in sorted(by_backend.items())
        },
        "rendered_pdf_count_by_backend": {
            backend: sum(1 for row in backend_rows if row.rendered_pdf_path)
            for backend, backend_rows in sorted(by_backend.items())
        },
        "top_error_reasons": dict(errors.most_common(10)),
    }


def write_bakeoff_artifacts(
    samples: Iterable[BakeoffSample],
    results: Iterable[BakeoffResult],
    out_dir: Path | str,
) -> dict[str, Any]:
    sample_rows = [asdict(sample) for sample in samples]
    result_rows = list(results)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "samples.json").write_text(
        json.dumps(sample_rows, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out / "results.jsonl").open("w", encoding="utf-8") as f:
        for row in result_rows:
            f.write(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True) + "\n")
    summary = summarize_bakeoff_results(result_rows)
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
