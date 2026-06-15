# Parser/Render Bakeoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic parser/render bakeoff harness that compares available HWP/HWPX parser and renderer backends on representative RFP samples without changing the CSV-first RAG path.

**Architecture:** Add a focused `rfp_rag.parser_bakeoff` module for sample selection, backend execution, result records, summaries, and artifact writing. Add a thin `rfp_rag.run_parser_bakeoff` CLI that loads corpus metadata plus the prior `parsed_docs` manifest, runs selected backends, writes ignored artifacts under `artifacts/parser_bakeoff`, and prints summary JSON. Optional backends must degrade to `missing_dependency` instead of failing the run.

**Tech Stack:** Python 3.11 stdlib, existing `rfp_rag.corpus`, existing `artifacts/parsed_docs/manifest.jsonl`, local `hwp5txt`/`hwp5html`/`hwp5odt`, optional `rhwp`, optional `unhwp` CLI, optional `hwpxkit`, optional LibreOffice `soffice`, pytest with monkeypatched backend runners.

---

## File Structure

- Create `rfp_rag/parser_bakeoff.py`
  - constants and dataclasses for samples/results
  - deterministic sample selection
  - backend registry and backend runners
  - result metric extraction
  - artifact writing and summary aggregation
- Create `rfp_rag/run_parser_bakeoff.py`
  - CLI wrapper and importable `run_parser_bakeoff(...)`
- Create `tests/test_parser_bakeoff.py`
  - core sample selection, result schema, summary, backend missing-dependency tests
- Create `tests/test_parser_bakeoff_cli.py`
  - CLI-level tests with fake backend registry
- Modify `REPORT.md`
  - add parser/render bakeoff section after a real smoke run
- Modify `README.md`
  - add command under source parsing lane or a new parser/render bakeoff section

Out of scope for this PR:

- replacing `build_index` input source
- adding permanent parser plugin abstraction
- installing commercial Hancom SDK
- requiring optional parser dependencies for tests
- committing generated artifacts

---

### Task 1: Bakeoff Core And Sample Selection

**Files:**
- Create: `rfp_rag/parser_bakeoff.py`
- Test: `tests/test_parser_bakeoff.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_parser_bakeoff.py` with these initial tests:

```python
from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.corpus import CorpusDocument
from rfp_rag.parser_bakeoff import (
    BAKEOFF_BACKEND_ERROR,
    BAKEOFF_EMPTY_OUTPUT,
    BAKEOFF_MISSING_DEPENDENCY,
    BAKEOFF_OK,
    BAKEOFF_UNSUPPORTED_FORMAT,
    BakeoffResult,
    BakeoffSample,
    select_bakeoff_samples,
    summarize_bakeoff_results,
    write_bakeoff_artifacts,
)


def _doc(idx: int, suffix: str = ".hwp", text: str = "CSV 본문") -> CorpusDocument:
    return CorpusDocument(
        csv_row_id=f"{idx:03d}",
        doc_id=f"doc:{idx:03d}",
        text=text,
        metadata={
            "project_name": f"사업 {idx}",
            "issuer": "기관",
            "resolved_filesystem_path": f"data/files/sample-{idx:03d}{suffix}",
            "csv_filename_raw": f"sample-{idx:03d}{suffix}",
        },
    )


def _manifest_row(
    idx: int,
    *,
    status: str = "parsed",
    text_length: int = 1000,
    csv_text_length: int = 100,
    ratio: float | None = 10.0,
    suffix: str = ".hwp",
) -> dict[str, object]:
    return {
        "doc_id": f"doc:{idx:03d}",
        "source_path": f"data/files/sample-{idx:03d}{suffix}",
        "source_suffix": suffix,
        "parse_status": status,
        "text_length": text_length,
        "csv_text_length": csv_text_length,
        "parsed_to_csv_length_ratio": ratio,
        "error_reason": None if status == "parsed" else status,
    }


def test_select_bakeoff_samples_includes_failures_large_ratio_median_and_pdfs() -> None:
    docs = [_doc(i) for i in range(14)] + [_doc(100 + i, ".pdf") for i in range(4)]
    manifest = [_manifest_row(i, text_length=1000 + i, ratio=1.0 + i / 10) for i in range(14)]
    manifest[2] = _manifest_row(2, status="empty_text", text_length=0, ratio=None)
    manifest[3] = _manifest_row(3, status="parser_error", text_length=0, ratio=None)
    manifest[10] = _manifest_row(10, text_length=9000, ratio=20.0)
    manifest[11] = _manifest_row(11, text_length=8000, ratio=30.0)
    manifest.extend(_manifest_row(100 + i, status="unsupported_suffix", suffix=".pdf", ratio=None) for i in range(4))

    samples = select_bakeoff_samples(docs, manifest, hwp_limit=6, include_pdfs=True)

    sample_ids = [sample.doc_id for sample in samples]
    assert "doc:002" in sample_ids
    assert "doc:003" in sample_ids
    assert "doc:010" in sample_ids
    assert "doc:011" in sample_ids
    assert {"doc:100", "doc:101", "doc:102", "doc:103"}.issubset(sample_ids)
    assert len([sample for sample in samples if sample.source_suffix == ".hwp"]) == 6
    assert len([sample for sample in samples if sample.source_suffix == ".pdf"]) == 4
    assert sample_ids == sorted(sample_ids)


def test_summarize_bakeoff_results_counts_statuses_and_backend_metrics() -> None:
    results = [
        BakeoffResult(
            doc_id="doc:000",
            source_path="a.hwp",
            source_suffix=".hwp",
            backend="hwp5txt",
            status=BAKEOFF_OK,
            elapsed_ms=10,
            text_path="out/a.txt",
            markdown_path=None,
            html_path=None,
            json_path=None,
            rendered_pdf_path=None,
            rendered_svg_count=0,
            rendered_png_count=0,
            asset_count=0,
            text_length=100,
            markdown_length=0,
            html_length=0,
            json_length=0,
            table_count=0,
            image_count=0,
            page_count=None,
            stdout_length=0,
            stderr_length=0,
            error_reason=None,
        ),
        BakeoffResult(
            doc_id="doc:001",
            source_path="b.pdf",
            source_suffix=".pdf",
            backend="hwp5txt",
            status=BAKEOFF_UNSUPPORTED_FORMAT,
            elapsed_ms=1,
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
            stdout_length=0,
            stderr_length=0,
            error_reason="unsupported suffix: .pdf",
        ),
        BakeoffResult(
            doc_id="doc:000",
            source_path="a.hwp",
            source_suffix=".hwp",
            backend="rhwp",
            status=BAKEOFF_MISSING_DEPENDENCY,
            elapsed_ms=0,
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
            stdout_length=0,
            stderr_length=0,
            error_reason="rhwp not installed",
        ),
    ]

    summary = summarize_bakeoff_results(results)

    assert summary["result_count"] == 3
    assert summary["backend_counts"] == {"hwp5txt": 2, "rhwp": 1}
    assert summary["status_counts"] == {
        BAKEOFF_MISSING_DEPENDENCY: 1,
        BAKEOFF_OK: 1,
        BAKEOFF_UNSUPPORTED_FORMAT: 1,
    }
    assert summary["backend_status_counts"]["hwp5txt"] == {BAKEOFF_OK: 1, BAKEOFF_UNSUPPORTED_FORMAT: 1}
    assert summary["backend_success_rate"]["hwp5txt"] == 0.5
    assert summary["backend_success_rate"]["rhwp"] == 0.0
    assert summary["text_length_by_backend"]["hwp5txt"]["max"] == 100
    assert summary["top_error_reasons"] == {"rhwp not installed": 1, "unsupported suffix: .pdf": 1}


def test_write_bakeoff_artifacts_writes_samples_results_and_summary(tmp_path: Path) -> None:
    samples = [
        BakeoffSample(
            doc_id="doc:000",
            csv_row_id="000",
            source_path="a.hwp",
            source_suffix=".hwp",
            project_name="사업",
            issuer="기관",
            csv_text_length=100,
            prior_parse_status="parsed",
            prior_text_length=1000,
            prior_ratio=10.0,
            selection_reasons=["large_text"],
        )
    ]
    results = [
        BakeoffResult(
            doc_id="doc:000",
            source_path="a.hwp",
            source_suffix=".hwp",
            backend="hwp5txt",
            status=BAKEOFF_OK,
            elapsed_ms=10,
            text_path="out/a.txt",
            markdown_path=None,
            html_path=None,
            json_path=None,
            rendered_pdf_path=None,
            rendered_svg_count=0,
            rendered_png_count=0,
            asset_count=0,
            text_length=100,
            markdown_length=0,
            html_length=0,
            json_length=0,
            table_count=0,
            image_count=0,
            page_count=None,
            stdout_length=0,
            stderr_length=0,
            error_reason=None,
        )
    ]

    summary = write_bakeoff_artifacts(samples, results, tmp_path / "bakeoff")

    assert (tmp_path / "bakeoff" / "samples.json").is_file()
    assert (tmp_path / "bakeoff" / "results.jsonl").is_file()
    assert (tmp_path / "bakeoff" / "summary.json").is_file()
    assert json.loads((tmp_path / "bakeoff" / "samples.json").read_text(encoding="utf-8"))[0]["doc_id"] == "doc:000"
    assert json.loads((tmp_path / "bakeoff" / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])["backend"] == "hwp5txt"
    assert json.loads((tmp_path / "bakeoff" / "summary.json").read_text(encoding="utf-8")) == summary
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'rfp_rag.parser_bakeoff'`.

- [ ] **Step 3: Implement core sample/result logic**

Create `rfp_rag/parser_bakeoff.py` with:

```python
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterable

from .corpus import CorpusDocument

BAKEOFF_OK = "ok"
BAKEOFF_MISSING_DEPENDENCY = "missing_dependency"
BAKEOFF_UNSUPPORTED_FORMAT = "unsupported_format"
BAKEOFF_EMPTY_OUTPUT = "empty_output"
BAKEOFF_TIMEOUT = "timeout"
BAKEOFF_BACKEND_ERROR = "backend_error"


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

    hwp_docs = [doc for doc in doc_list if str(doc.metadata.get("resolved_filesystem_path") or "").lower().endswith(".hwp")]
    pdf_docs = [doc for doc in doc_list if str(doc.metadata.get("resolved_filesystem_path") or "").lower().endswith(".pdf")]

    for doc in hwp_docs:
        row = manifest.get(doc.doc_id, {})
        if row.get("parse_status") in {"empty_text", "parser_error"}:
            reasons_by_doc[doc.doc_id].add(str(row.get("parse_status")))

    for doc in sorted(hwp_docs, key=lambda item: int(manifest.get(item.doc_id, {}).get("text_length") or 0), reverse=True)[:4]:
        reasons_by_doc[doc.doc_id].add("large_text")

    ratio_docs = [
        doc
        for doc in hwp_docs
        if manifest.get(doc.doc_id, {}).get("parsed_to_csv_length_ratio") is not None
    ]
    for doc in sorted(ratio_docs, key=lambda item: float(manifest[item.doc_id]["parsed_to_csv_length_ratio"]), reverse=True)[:4]:
        reasons_by_doc[doc.doc_id].add("high_ratio")

    parsed_hwp_docs = [doc for doc in hwp_docs if manifest.get(doc.doc_id, {}).get("parse_status") == "parsed"]
    parsed_hwp_docs = sorted(parsed_hwp_docs, key=lambda item: int(manifest.get(item.doc_id, {}).get("text_length") or 0))
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/parser_bakeoff.py tests/test_parser_bakeoff.py
git commit -m "feat: add parser bakeoff core"
```

---

### Task 2: Backend Runner Implementations

**Files:**
- Modify: `rfp_rag/parser_bakeoff.py`
- Test: `tests/test_parser_bakeoff.py`

- [ ] **Step 1: Add failing backend tests**

Append these tests to `tests/test_parser_bakeoff.py`:

```python
import subprocess

from rfp_rag.parser_bakeoff import (
    run_backend_for_sample,
    run_command_backend,
    run_optional_import_backend,
)


def test_run_command_backend_writes_text_output(tmp_path: Path) -> None:
    sample = BakeoffSample(
        doc_id="doc:000",
        csv_row_id="000",
        source_path=str(tmp_path / "a.hwp"),
        source_suffix=".hwp",
        project_name="사업",
        issuer="기관",
        csv_text_length=100,
        prior_parse_status="parsed",
        prior_text_length=1000,
        prior_ratio=10.0,
        selection_reasons=["large_text"],
    )
    Path(sample.source_path).write_bytes(b"hwp")

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="본문", stderr="warn")

    result = run_command_backend(
        sample,
        backend="hwp5txt",
        command=["hwp5txt", sample.source_path],
        out_dir=tmp_path / "out",
        timeout_seconds=5,
        runner=runner,
        output_kind="text",
    )

    assert result.status == BAKEOFF_OK
    assert result.text_length == len("본문")
    assert result.stderr_length == len("warn")
    assert result.text_path is not None
    assert Path(result.text_path).read_text(encoding="utf-8") == "본문\n"


def test_run_command_backend_records_empty_output(tmp_path: Path) -> None:
    sample = BakeoffSample(
        doc_id="doc:000",
        csv_row_id="000",
        source_path=str(tmp_path / "a.hwp"),
        source_suffix=".hwp",
        project_name="사업",
        issuer="기관",
        csv_text_length=100,
        prior_parse_status="parsed",
        prior_text_length=1000,
        prior_ratio=10.0,
        selection_reasons=["large_text"],
    )
    Path(sample.source_path).write_bytes(b"hwp")

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=" \n", stderr="")

    result = run_command_backend(
        sample,
        backend="hwp5txt",
        command=["hwp5txt", sample.source_path],
        out_dir=tmp_path / "out",
        timeout_seconds=5,
        runner=runner,
        output_kind="text",
    )

    assert result.status == BAKEOFF_EMPTY_OUTPUT
    assert result.error_reason == "empty output"


def test_run_command_backend_records_missing_dependency(tmp_path: Path) -> None:
    sample = BakeoffSample(
        doc_id="doc:000",
        csv_row_id="000",
        source_path=str(tmp_path / "a.hwp"),
        source_suffix=".hwp",
        project_name="사업",
        issuer="기관",
        csv_text_length=100,
        prior_parse_status="parsed",
        prior_text_length=1000,
        prior_ratio=10.0,
        selection_reasons=["large_text"],
    )
    Path(sample.source_path).write_bytes(b"hwp")

    def runner(*args, **kwargs):
        raise FileNotFoundError("missing")

    result = run_command_backend(
        sample,
        backend="hwp5txt",
        command=["hwp5txt", sample.source_path],
        out_dir=tmp_path / "out",
        timeout_seconds=5,
        runner=runner,
        output_kind="text",
    )

    assert result.status == BAKEOFF_MISSING_DEPENDENCY
    assert result.error_reason == "hwp5txt not found"


def test_run_backend_for_sample_marks_hwp5txt_pdf_unsupported(tmp_path: Path) -> None:
    sample = BakeoffSample(
        doc_id="doc:007",
        csv_row_id="007",
        source_path=str(tmp_path / "a.pdf"),
        source_suffix=".pdf",
        project_name="사업",
        issuer="기관",
        csv_text_length=100,
        prior_parse_status="unsupported_suffix",
        prior_text_length=0,
        prior_ratio=None,
        selection_reasons=["pdf_reference"],
    )
    Path(sample.source_path).write_bytes(b"pdf")

    result = run_backend_for_sample(sample, backend="hwp5txt", out_dir=tmp_path / "out", timeout_seconds=5)

    assert result.status == BAKEOFF_UNSUPPORTED_FORMAT
    assert result.error_reason == "hwp5txt supports only .hwp"


def test_run_optional_import_backend_records_missing_module(tmp_path: Path) -> None:
    sample = BakeoffSample(
        doc_id="doc:000",
        csv_row_id="000",
        source_path=str(tmp_path / "a.hwp"),
        source_suffix=".hwp",
        project_name="사업",
        issuer="기관",
        csv_text_length=100,
        prior_parse_status="parsed",
        prior_text_length=1000,
        prior_ratio=10.0,
        selection_reasons=["large_text"],
    )

    result = run_optional_import_backend(
        sample,
        backend="rhwp",
        module_name="definitely_missing_rhwp_module",
        out_dir=tmp_path / "out",
    )

    assert result.status == BAKEOFF_MISSING_DEPENDENCY
    assert result.error_reason == "definitely_missing_rhwp_module not installed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py -q
```

Expected: FAIL with missing backend runner symbols.

- [ ] **Step 3: Implement backend runners**

Add to `rfp_rag/parser_bakeoff.py`:

```python
import importlib
import shutil
import subprocess
import time
from typing import Callable

Runner = Callable[..., subprocess.CompletedProcess[Any]]


def _safe_filename(doc_id: str, suffix: str) -> str:
    return f"{doc_id.replace(':', '_')}{suffix}"


def _text_or_empty(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _normalize_text(value: Any) -> str:
    return _text_or_empty(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def _empty_result(
    sample: BakeoffSample,
    *,
    backend: str,
    status: str,
    elapsed_ms: int = 0,
    stdout: str = "",
    stderr: str = "",
    error_reason: str | None,
) -> BakeoffResult:
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
        stdout_length=len(stdout),
        stderr_length=len(stderr),
        error_reason=error_reason,
    )


def _write_output(out_dir: Path, backend: str, sample: BakeoffSample, output_kind: str, text: str) -> tuple[str | None, str | None, str | None]:
    backend_dir = out_dir / "backends" / backend
    backend_dir.mkdir(parents=True, exist_ok=True)
    if output_kind == "text":
        path = backend_dir / _safe_filename(sample.doc_id, ".txt")
        path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
        return str(path), None, None
    if output_kind == "html":
        path = backend_dir / _safe_filename(sample.doc_id, ".html")
        path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
        return None, None, str(path)
    if output_kind == "markdown":
        path = backend_dir / _safe_filename(sample.doc_id, ".md")
        path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
        return None, str(path), None
    raise ValueError(f"unknown output kind: {output_kind}")


def run_command_backend(
    sample: BakeoffSample,
    *,
    backend: str,
    command: list[str],
    out_dir: Path | str,
    timeout_seconds: int,
    runner: Runner = subprocess.run,
    output_kind: str,
) -> BakeoffResult:
    out = Path(out_dir)
    start = time.perf_counter()
    try:
        completed = runner(command, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except FileNotFoundError:
        return _empty_result(sample, backend=backend, status=BAKEOFF_MISSING_DEPENDENCY, error_reason=f"{command[0]} not found")
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return _empty_result(
            sample,
            backend=backend,
            status=BAKEOFF_TIMEOUT,
            elapsed_ms=elapsed_ms,
            stdout=_text_or_empty(exc.stdout),
            stderr=_text_or_empty(exc.stderr),
            error_reason=f"backend timeout after {timeout_seconds}s",
        )
    except OSError as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return _empty_result(sample, backend=backend, status=BAKEOFF_BACKEND_ERROR, elapsed_ms=elapsed_ms, error_reason=str(exc))

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    stdout = _text_or_empty(completed.stdout)
    stderr = _text_or_empty(completed.stderr)
    output = _normalize_text(stdout)
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
    if not output:
        return _empty_result(
            sample,
            backend=backend,
            status=BAKEOFF_EMPTY_OUTPUT,
            elapsed_ms=elapsed_ms,
            stdout=stdout,
            stderr=stderr,
            error_reason="empty output",
        )
    text_path, markdown_path, html_path = _write_output(out, backend, sample, output_kind, output)
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
        json_path=None,
        rendered_pdf_path=None,
        rendered_svg_count=0,
        rendered_png_count=0,
        asset_count=0,
        text_length=len(output) if output_kind == "text" else 0,
        markdown_length=len(output) if output_kind == "markdown" else 0,
        html_length=len(output) if output_kind == "html" else 0,
        json_length=0,
        table_count=output.lower().count("<table"),
        image_count=output.lower().count("<img"),
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
        importlib.import_module(module_name)
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
        return _empty_result(sample, backend=backend, status=BAKEOFF_UNSUPPORTED_FORMAT, error_reason=f"{backend} supports only .hwp")
    if backend == "hwp5txt":
        return run_command_backend(sample, backend=backend, command=["hwp5txt", sample.source_path], out_dir=out_dir, timeout_seconds=timeout_seconds, output_kind="text")
    if backend == "hwp5html":
        return run_command_backend(sample, backend=backend, command=["hwp5html", "--html", sample.source_path], out_dir=out_dir, timeout_seconds=timeout_seconds, output_kind="html")
    if backend == "hwp5odt":
        return run_command_backend(sample, backend=backend, command=["hwp5odt", "--document", sample.source_path], out_dir=out_dir, timeout_seconds=timeout_seconds, output_kind="html")
    if backend == "rhwp":
        return run_optional_import_backend(sample, backend=backend, module_name="rhwp", out_dir=out_dir)
    if backend == "unhwp":
        if shutil.which("unhwp") is None:
            return _empty_result(sample, backend=backend, status=BAKEOFF_MISSING_DEPENDENCY, error_reason="unhwp not found")
        return run_command_backend(sample, backend=backend, command=["unhwp", sample.source_path], out_dir=out_dir, timeout_seconds=timeout_seconds, output_kind="markdown")
    if backend == "hwpxkit":
        return run_optional_import_backend(sample, backend=backend, module_name="hwpxkit", out_dir=out_dir)
    if backend == "libreoffice_pdf":
        if suffix != ".hwp":
            return _empty_result(sample, backend=backend, status=BAKEOFF_UNSUPPORTED_FORMAT, error_reason="libreoffice_pdf supports only .hwp")
        if shutil.which("soffice") is None and shutil.which("libreoffice") is None:
            return _empty_result(sample, backend=backend, status=BAKEOFF_MISSING_DEPENDENCY, error_reason="soffice not found")
        return _empty_result(sample, backend=backend, status=BAKEOFF_BACKEND_ERROR, error_reason="libreoffice_pdf runner not implemented in first bakeoff")
    return _empty_result(sample, backend=backend, status=BAKEOFF_BACKEND_ERROR, error_reason=f"unknown backend: {backend}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/parser_bakeoff.py tests/test_parser_bakeoff.py
git commit -m "feat: add parser bakeoff backends"
```

---

### Task 3: Bakeoff CLI

**Files:**
- Create: `rfp_rag/run_parser_bakeoff.py`
- Test: `tests/test_parser_bakeoff_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_parser_bakeoff_cli.py`:

```python
from __future__ import annotations

import csv
import json
from pathlib import Path

from rfp_rag import run_parser_bakeoff as cli_module
from rfp_rag.parser_bakeoff import BAKEOFF_OK, BakeoffResult
from rfp_rag.run_parser_bakeoff import main, run_parser_bakeoff


FIELDNAMES = [
    "공고 번호",
    "공고 차수",
    "사업명",
    "사업 금액",
    "발주 기관",
    "공개 일자",
    "입찰 참여 시작일",
    "입찰 참여 마감일",
    "사업 요약",
    "파일형식",
    "파일명",
    "텍스트",
]


def _write_csv(path: Path, filenames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for idx, filename in enumerate(filenames):
            writer.writerow({
                "공고 번호": str(idx),
                "공고 차수": "0",
                "사업명": f"사업 {idx}",
                "사업 금액": "1000",
                "발주 기관": "기관",
                "공개 일자": "",
                "입찰 참여 시작일": "",
                "입찰 참여 마감일": "",
                "사업 요약": "요약",
                "파일형식": Path(filename).suffix.lstrip("."),
                "파일명": filename,
                "텍스트": "CSV 본문",
            })


def _write_manifest(path: Path, filenames: list[str]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for idx, filename in enumerate(filenames):
            suffix = Path(filename).suffix.lower()
            f.write(json.dumps({
                "doc_id": f"doc:{idx:03d}",
                "source_path": str(path.parent / "files" / filename),
                "source_suffix": suffix,
                "parse_status": "parsed" if suffix == ".hwp" else "unsupported_suffix",
                "text_length": 1000 + idx,
                "csv_text_length": 100,
                "parsed_to_csv_length_ratio": 10.0 + idx,
                "error_reason": None,
            }, ensure_ascii=False) + "\n")


def test_run_parser_bakeoff_writes_artifacts_with_fake_backend(tmp_path: Path, monkeypatch) -> None:
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    for filename in ["a.hwp", "b.hwp", "c.pdf"]:
        (files_dir / filename).write_bytes(b"file")
    csv_path = tmp_path / "data.csv"
    manifest_path = tmp_path / "manifest.jsonl"
    _write_csv(csv_path, ["a.hwp", "b.hwp", "c.pdf"])
    _write_manifest(manifest_path, ["a.hwp", "b.hwp", "c.pdf"])

    def fake_run_backend_for_sample(sample, *, backend: str, out_dir: Path | str, timeout_seconds: int = 60):
        return BakeoffResult(
            doc_id=sample.doc_id,
            source_path=sample.source_path,
            source_suffix=sample.source_suffix,
            backend=backend,
            status=BAKEOFF_OK,
            elapsed_ms=1,
            text_path=None,
            markdown_path=None,
            html_path=None,
            json_path=None,
            rendered_pdf_path=None,
            rendered_svg_count=0,
            rendered_png_count=0,
            asset_count=0,
            text_length=123,
            markdown_length=0,
            html_length=0,
            json_length=0,
            table_count=0,
            image_count=0,
            page_count=None,
            stdout_length=0,
            stderr_length=0,
            error_reason=None,
        )

    monkeypatch.setattr(cli_module, "run_backend_for_sample", fake_run_backend_for_sample)

    summary = run_parser_bakeoff(
        csv_path,
        files_dir,
        manifest_path,
        tmp_path / "out",
        backends=["fake"],
        hwp_limit=2,
        include_pdfs=True,
        timeout_seconds=3,
    )

    assert summary["result_count"] == 3
    assert json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8")) == summary
    assert len(json.loads((tmp_path / "out" / "samples.json").read_text(encoding="utf-8"))) == 3
    assert len((tmp_path / "out" / "results.jsonl").read_text(encoding="utf-8").splitlines()) == 3


def test_main_prints_summary_json(tmp_path: Path, monkeypatch, capsys) -> None:
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    (files_dir / "a.hwp").write_bytes(b"hwp")
    csv_path = tmp_path / "data.csv"
    manifest_path = tmp_path / "manifest.jsonl"
    _write_csv(csv_path, ["a.hwp"])
    _write_manifest(manifest_path, ["a.hwp"])

    def fake_run_backend_for_sample(sample, *, backend: str, out_dir: Path | str, timeout_seconds: int = 60):
        return BakeoffResult(
            doc_id=sample.doc_id,
            source_path=sample.source_path,
            source_suffix=sample.source_suffix,
            backend=backend,
            status=BAKEOFF_OK,
            elapsed_ms=1,
            text_path=None,
            markdown_path=None,
            html_path=None,
            json_path=None,
            rendered_pdf_path=None,
            rendered_svg_count=0,
            rendered_png_count=0,
            asset_count=0,
            text_length=123,
            markdown_length=0,
            html_length=0,
            json_length=0,
            table_count=0,
            image_count=0,
            page_count=None,
            stdout_length=0,
            stderr_length=0,
            error_reason=None,
        )

    monkeypatch.setattr(cli_module, "run_backend_for_sample", fake_run_backend_for_sample)

    rc = main([
        "--data", str(csv_path),
        "--files", str(files_dir),
        "--parse-manifest", str(manifest_path),
        "--out", str(tmp_path / "out"),
        "--backend", "fake",
        "--hwp-limit", "1",
        "--timeout-seconds", "2",
    ])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["result_count"] == 1
    assert payload["backend_counts"] == {"fake": 1}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff_cli.py -q
```

Expected: FAIL with missing `rfp_rag.run_parser_bakeoff`.

- [ ] **Step 3: Implement CLI**

Create `rfp_rag/run_parser_bakeoff.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .corpus import load_corpus
from .parser_bakeoff import (
    load_parse_manifest,
    run_backend_for_sample,
    select_bakeoff_samples,
    write_bakeoff_artifacts,
)

DEFAULT_BACKENDS = ["hwp5txt", "hwp5html", "hwp5odt", "rhwp", "unhwp", "hwpxkit", "libreoffice_pdf"]


def run_parser_bakeoff(
    data_path: Path | str,
    files_path: Path | str,
    parse_manifest_path: Path | str,
    out_dir: Path | str,
    *,
    backends: list[str] | None = None,
    hwp_limit: int = 12,
    include_pdfs: bool = True,
    timeout_seconds: int = 60,
) -> dict[str, object]:
    docs = load_corpus(data_path, files_path)
    manifest_rows = load_parse_manifest(parse_manifest_path)
    samples = select_bakeoff_samples(docs, manifest_rows, hwp_limit=hwp_limit, include_pdfs=include_pdfs)
    selected_backends = backends or DEFAULT_BACKENDS
    results = []
    for sample in samples:
        for backend in selected_backends:
            results.append(
                run_backend_for_sample(
                    sample,
                    backend=backend,
                    out_dir=out_dir,
                    timeout_seconds=timeout_seconds,
                )
            )
    return write_bakeoff_artifacts(samples, results, out_dir)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run parser/render bakeoff on representative RFP source files.")
    parser.add_argument("--data", required=True, type=Path, help="Path to data_list.csv")
    parser.add_argument("--files", required=True, type=Path, help="Path to source file directory")
    parser.add_argument("--parse-manifest", required=True, type=Path, help="Path to artifacts/parsed_docs/manifest.jsonl")
    parser.add_argument("--out", required=True, type=Path, help="Bakeoff artifact output directory")
    parser.add_argument("--backend", action="append", dest="backends", help="Backend to run; repeat for multiple backends")
    parser.add_argument("--hwp-limit", default=12, type=int, help="Number of HWP samples")
    parser.add_argument("--timeout-seconds", default=60, type=int, help="Per backend/sample timeout")
    parser.add_argument("--no-pdfs", action="store_true", help="Exclude PDF reference samples")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    summary = run_parser_bakeoff(
        args.data,
        args.files,
        args.parse_manifest,
        args.out,
        backends=args.backends,
        hwp_limit=args.hwp_limit,
        include_pdfs=not args.no_pdfs,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py tests/test_parser_bakeoff_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/run_parser_bakeoff.py tests/test_parser_bakeoff_cli.py
git commit -m "feat: add parser bakeoff CLI"
```

---

### Task 4: Smoke Run And Documentation

**Files:**
- Modify: `README.md`
- Modify: `REPORT.md`

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py tests/test_parser_bakeoff_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run bakeoff smoke with safe baseline backends**

Run:

```bash
uv run --group dev python -m rfp_rag.run_parser_bakeoff \
  --data data/data_list.csv \
  --files data/files \
  --parse-manifest artifacts/parsed_docs/manifest.jsonl \
  --out artifacts/parser_bakeoff \
  --backend hwp5txt \
  --backend hwp5html \
  --backend hwp5odt \
  --backend rhwp \
  --backend unhwp \
  --backend hwpxkit \
  --backend libreoffice_pdf \
  --timeout-seconds 20
```

Expected:

- exits `0`
- writes `artifacts/parser_bakeoff/samples.json`
- writes `artifacts/parser_bakeoff/results.jsonl`
- writes `artifacts/parser_bakeoff/summary.json`
- optional backends not installed are recorded as `missing_dependency`

- [ ] **Step 3: Extract bakeoff summary**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path("artifacts/parser_bakeoff/summary.json").read_text(encoding="utf-8"))
print(json.dumps({
    "result_count": summary["result_count"],
    "backend_counts": summary["backend_counts"],
    "status_counts": summary["status_counts"],
    "backend_success_rate": summary["backend_success_rate"],
    "rendered_pdf_count_by_backend": summary["rendered_pdf_count_by_backend"],
    "top_error_reasons": summary["top_error_reasons"],
}, ensure_ascii=False, indent=2, sort_keys=True))
PY
```

- [ ] **Step 4: Update README**

Add under the source parsing section:

```markdown
## Parser/render bakeoff

Before parsed HWP output becomes an index source, the project compares parser and
renderer backends on representative RFP samples.

```bash
python3 -m rfp_rag.run_parser_bakeoff \
  --data data/data_list.csv \
  --files data/files \
  --parse-manifest artifacts/parsed_docs/manifest.jsonl \
  --out artifacts/parser_bakeoff
```

Outputs:

- `artifacts/parser_bakeoff/samples.json`
- `artifacts/parser_bakeoff/results.jsonl`
- `artifacts/parser_bakeoff/summary.json`

Optional backends such as `rhwp`, `unhwp`, `hwpxkit`, and LibreOffice are recorded
as `missing_dependency` when unavailable, so the bakeoff remains reproducible on
a minimal local setup.
```

- [ ] **Step 5: Update REPORT**

Add a section after `### 10-17. Source Parsing Lane` and before `## 11. 결론`:

Use the JSON printed in Step 3 to render each value as compact JSON with
`ensure_ascii=False` and `sort_keys=True`. The resulting section must follow this
shape:

```markdown
### 10-18. Parser/Render Bakeoff Lane

Source-aware indexing is intentionally blocked until parser/render quality is
measured. This lane compares text extraction and rendered evidence surfaces on a
deterministic subset of HWP/PDF RFP files.

| metric | value |
|---|---|
| result_count | value rendered from `summary["result_count"]` |
| backend_counts | value rendered from `summary["backend_counts"]` |
| status_counts | value rendered from `summary["status_counts"]` |
| backend_success_rate | value rendered from `summary["backend_success_rate"]` |
| rendered_pdf_count_by_backend | value rendered from `summary["rendered_pdf_count_by_backend"]` |
| top_error_reasons | value rendered from `summary["top_error_reasons"]` |

재현 커맨드:

```bash
python3 -m rfp_rag.run_parser_bakeoff \
  --data data/data_list.csv \
  --files data/files \
  --parse-manifest artifacts/parsed_docs/manifest.jsonl \
  --out artifacts/parser_bakeoff
```

해석:

- `hwp5txt`, `hwp5html`, `hwp5odt`는 로컬 baseline이다.
- `rhwp`, `unhwp`, `hwpxkit`, LibreOffice는 설치되어 있으면 비교하고, 없으면
  `missing_dependency`로 기록한다.
- 다음 단계의 `--source parsed` indexing은 이 bakeoff 결과를 기준으로 backend를 선택한다.
```

This command prints the metric table body in the expected format:

```bash
python3 - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path("artifacts/parser_bakeoff/summary.json").read_text(encoding="utf-8"))
for key in [
    "result_count",
    "backend_counts",
    "status_counts",
    "backend_success_rate",
    "rendered_pdf_count_by_backend",
    "top_error_reasons",
]:
    value = json.dumps(summary[key], ensure_ascii=False, sort_keys=True)
    print(f"| {key} | `{value}` |")
PY
```

- [ ] **Step 6: Run docs checks**

Run:

```bash
uv run --group dev python -m rfp_rag.report_check --eval artifacts/eval --readme README.md
rg -n "Parser/render bakeoff|run_parser_bakeoff|parser_bakeoff|10-18" README.md REPORT.md
```

Expected:

- report check returns `"ok": true`
- ripgrep finds the new docs

- [ ] **Step 7: Commit docs**

```bash
git add README.md REPORT.md
git commit -m "docs: record parser render bakeoff smoke"
```

---

### Task 5: Final Verification And PR

**Files:**
- No code changes unless verification finds a defect.

- [ ] **Step 1: Run full credential-free tests**

Run:

```bash
uv run --group dev python -m pytest -m "not real" -q
```

Expected: PASS.

- [ ] **Step 2: Verify artifacts exist locally and remain ignored**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

for path in [
    Path("artifacts/parser_bakeoff/samples.json"),
    Path("artifacts/parser_bakeoff/results.jsonl"),
    Path("artifacts/parser_bakeoff/summary.json"),
]:
    print(path, path.exists())
PY
git status --short
git status --short --ignored=matching | rg "artifacts/" || true
```

Expected:

- three artifact files exist
- normal `git status --short` is clean after committed changes
- ignored status shows `artifacts/`

- [ ] **Step 3: Push branch**

Run:

```bash
git push -u origin feature/parser-render-bakeoff-lane
```

Expected: push succeeds.

- [ ] **Step 4: Open draft PR**

Run:

```bash
gh pr create --draft --base master --head feature/parser-render-bakeoff-lane \
  --title "Add parser render bakeoff lane" \
  --body-file -
```

Use this PR body:

```markdown
## Summary
- Add parser/render bakeoff harness for representative HWP/PDF RFP samples.
- Compare local HWP parser baselines and optional modern HWP/HWPX backends without requiring optional dependencies.
- Record bakeoff smoke results and keep generated artifacts ignored.

## Verification
- `uv run --group dev python -m pytest tests/test_parser_bakeoff.py tests/test_parser_bakeoff_cli.py -q`
- `uv run --group dev python -m rfp_rag.report_check --eval artifacts/eval --readme README.md`
- `uv run --group dev python -m pytest -m "not real" -q`

## Notes
- This PR does not change `build_index` source selection.
- Optional parser/render backends are recorded as `missing_dependency` when unavailable.
```

---

## Test Plan

Run before final handoff:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py tests/test_parser_bakeoff_cli.py -q
uv run --group dev python -m rfp_rag.run_parser_bakeoff \
  --data data/data_list.csv \
  --files data/files \
  --parse-manifest artifacts/parsed_docs/manifest.jsonl \
  --out artifacts/parser_bakeoff \
  --timeout-seconds 20
uv run --group dev python -m rfp_rag.report_check --eval artifacts/eval --readme README.md
uv run --group dev python -m pytest -m "not real" -q
```

## Self-Review

- The plan implements the parser/render bakeoff spec without replacing CSV-first indexing.
- Optional dependencies are non-blocking and recorded as controlled statuses.
- Generated artifacts remain ignored.
- The plan creates portfolio evidence for parser fidelity, rendered evidence, and backend selection before source-aware indexing.
