# Parser Bakeoff Backend Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the parser/render bakeoff run real local adapters for the most relevant HWP/HWPX candidates instead of only reporting installed-but-unimplemented stubs.

**Architecture:** Keep `rfp_rag/parser_bakeoff.py` as the single bakeoff backend module. Add small helpers for executable discovery and multi-artifact result assembly, then wire concrete adapters for `rhwp`, `unhwp`, and LibreOffice without changing the index pipeline. Optional packages remain controlled `missing_dependency` results.

**Tech Stack:** Python 3.11+, pytest, local CLI tools (`unhwp`, LibreOffice `soffice`), optional Python modules (`rhwp`, `hwpxkit`, `hwpkit`), existing bakeoff artifact schema.

---

## File Structure

- Modify `rfp_rag/parser_bakeoff.py`
  - Add executable discovery helpers for app-bundle and cargo-bin tools.
  - Add artifact writing helpers for adapters that produce multiple files.
  - Implement `rhwp` adapter using `rhwp.parse()`, `extract_text()`, `to_ir_json()`, `export_pdf()`, `export_svg()`, and `export_png()`.
  - Implement `unhwp` adapter using `unhwp markdown`, `unhwp text`, and `unhwp json` stdout commands.
  - Implement `libreoffice_pdf` adapter using discovered `soffice`.
  - Add `hwpkit` as an optional backend candidate with controlled missing/stub behavior.
- Modify `rfp_rag/run_parser_bakeoff.py`
  - Add `hwpkit` to `DEFAULT_BACKENDS` only if the adapter is represented in `run_backend_for_sample()`.
- Modify `tests/test_parser_bakeoff.py`
  - Add tests for executable discovery.
  - Add tests for `rhwp` adapter with a fake module object.
  - Add tests for `unhwp` command routing.
  - Add tests for LibreOffice app-bundle discovery and conversion output handling.
  - Add tests for `hwpkit` optional backend behavior.
- Modify `tests/test_parser_bakeoff_cli.py`
  - Add `hwpkit` default backend coverage only if default backend list changes.
- Modify `REPORT.md`
  - Add a short note that backend expansion is now capable of measuring installed `rhwp`, `unhwp`, and LibreOffice.

## Task 1: Executable Discovery

**Files:**
- Modify: `rfp_rag/parser_bakeoff.py`
- Test: `tests/test_parser_bakeoff.py`

- [ ] **Step 1: Write failing tests for executable discovery**

Add this test to `tests/test_parser_bakeoff.py`:

```python
def test_find_executable_prefers_path_then_extra_candidates(tmp_path: Path, monkeypatch) -> None:
    from rfp_rag import parser_bakeoff

    extra = tmp_path / "tool"
    extra.write_text("#!/bin/sh\n", encoding="utf-8")
    extra.chmod(0o755)

    monkeypatch.setattr(parser_bakeoff.shutil, "which", lambda name: None)

    assert parser_bakeoff._find_executable("missing", extra_candidates=[extra]) == str(extra)
    assert parser_bakeoff._find_executable("missing", extra_candidates=[tmp_path / "absent"]) is None
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py::test_find_executable_prefers_path_then_extra_candidates -q
```

Expected: FAIL because `_find_executable` does not exist.

- [ ] **Step 3: Implement executable discovery**

Add this helper near `_safe_doc_stem()` in `rfp_rag/parser_bakeoff.py`:

```python
def _find_executable(name: str, *, extra_candidates: Iterable[Path | str] = ()) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for candidate in extra_candidates:
        path = Path(candidate).expanduser()
        if path.is_file():
            return str(path)
    return None
```

- [ ] **Step 4: Run the test**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py::test_find_executable_prefers_path_then_extra_candidates -q
```

Expected: PASS.

## Task 2: Multi-Artifact Result Helper

**Files:**
- Modify: `rfp_rag/parser_bakeoff.py`
- Test: `tests/test_parser_bakeoff.py`

- [ ] **Step 1: Write failing test for multi-artifact result assembly**

Add this test:

```python
def test_build_result_from_artifacts_counts_lengths_tables_images_and_renders(tmp_path: Path) -> None:
    sample = BakeoffSample(
        doc_id="doc:009",
        csv_row_id="009",
        source_path=str(tmp_path / "sample.hwp"),
        source_suffix=".hwp",
        project_name="사업",
        issuer="기관",
        csv_text_length=10,
        prior_parse_status="parsed",
        prior_text_length=100,
        prior_ratio=10.0,
        selection_reasons=["large_text"],
    )
    backend_dir = tmp_path / "out" / "backends" / "rhwp"
    backend_dir.mkdir(parents=True)
    text_path = backend_dir / "doc_009.txt"
    json_path = backend_dir / "doc_009.json"
    pdf_path = backend_dir / "doc_009.pdf"
    svg_path = backend_dir / "doc_009-1.svg"
    png_path = backend_dir / "doc_009-1.png"
    text_path.write_text("본문", encoding="utf-8")
    json_path.write_text('{"tables": [{"cells": []}], "images": ["a"]}', encoding="utf-8")
    pdf_path.write_bytes(b"%PDF")
    svg_path.write_text("<svg><image /></svg>", encoding="utf-8")
    png_path.write_bytes(b"png")

    from rfp_rag import parser_bakeoff

    result = parser_bakeoff._build_result_from_artifacts(
        sample,
        backend="rhwp",
        elapsed_ms=12,
        text_path=text_path,
        json_path=json_path,
        rendered_pdf_path=pdf_path,
        rendered_svg_paths=[svg_path],
        rendered_png_paths=[png_path],
        stdout="ok",
        stderr="warn",
        page_count=1,
    )

    assert result.status == BAKEOFF_OK
    assert result.text_length == len("본문")
    assert result.json_length == len('{"tables": [{"cells": []}], "images": ["a"]}')
    assert result.table_count == 1
    assert result.image_count == 2
    assert result.rendered_pdf_path == str(pdf_path)
    assert result.rendered_svg_count == 1
    assert result.rendered_png_count == 1
    assert result.page_count == 1
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py::test_build_result_from_artifacts_counts_lengths_tables_images_and_renders -q
```

Expected: FAIL because `_build_result_from_artifacts` does not exist.

- [ ] **Step 3: Implement artifact helper**

Add this helper after `run_command_backend()`:

```python
def _read_text_length(path: Path | None) -> int:
    if path is None or not path.is_file():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace"))


def _count_markers(*values: str) -> tuple[int, int]:
    joined = "\n".join(values).lower()
    table_count = joined.count("<table") + joined.count('"tables"') + joined.count("'tables'")
    image_count = joined.count("<img") + joined.count("<image") + joined.count('"images"') + joined.count("'images'")
    return table_count, image_count


def _build_result_from_artifacts(
    sample: BakeoffSample,
    *,
    backend: str,
    elapsed_ms: int,
    text_path: Path | None = None,
    markdown_path: Path | None = None,
    html_path: Path | None = None,
    json_path: Path | None = None,
    rendered_pdf_path: Path | None = None,
    rendered_svg_paths: Iterable[Path] = (),
    rendered_png_paths: Iterable[Path] = (),
    asset_count: int = 0,
    stdout: Any = "",
    stderr: Any = "",
    page_count: int | None = None,
) -> BakeoffResult:
    text_value = text_path.read_text(encoding="utf-8", errors="replace") if text_path and text_path.is_file() else ""
    markdown_value = (
        markdown_path.read_text(encoding="utf-8", errors="replace") if markdown_path and markdown_path.is_file() else ""
    )
    html_value = html_path.read_text(encoding="utf-8", errors="replace") if html_path and html_path.is_file() else ""
    json_value = json_path.read_text(encoding="utf-8", errors="replace") if json_path and json_path.is_file() else ""
    table_count, image_count = _count_markers(text_value, markdown_value, html_value, json_value)
    svg_rows = list(rendered_svg_paths)
    png_rows = list(rendered_png_paths)
    stdout_text = _stringify(stdout)
    stderr_text = _stringify(stderr)
    return BakeoffResult(
        doc_id=sample.doc_id,
        source_path=sample.source_path,
        source_suffix=sample.source_suffix,
        backend=backend,
        status=BAKEOFF_OK,
        elapsed_ms=elapsed_ms,
        text_path=str(text_path) if text_path else None,
        markdown_path=str(markdown_path) if markdown_path else None,
        html_path=str(html_path) if html_path else None,
        json_path=str(json_path) if json_path else None,
        rendered_pdf_path=str(rendered_pdf_path) if rendered_pdf_path else None,
        rendered_svg_count=len(svg_rows),
        rendered_png_count=len(png_rows),
        asset_count=asset_count,
        text_length=len(text_value),
        markdown_length=len(markdown_value),
        html_length=len(html_value),
        json_length=len(json_value),
        table_count=table_count,
        image_count=image_count,
        page_count=page_count,
        stdout_length=len(stdout_text),
        stderr_length=len(stderr_text),
        error_reason=None,
    )
```

- [ ] **Step 4: Run the test**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py::test_build_result_from_artifacts_counts_lengths_tables_images_and_renders -q
```

Expected: PASS.

## Task 3: rhwp Backend Adapter

**Files:**
- Modify: `rfp_rag/parser_bakeoff.py`
- Test: `tests/test_parser_bakeoff.py`

- [ ] **Step 1: Write failing fake-module test**

Add this test:

```python
def test_run_rhwp_backend_writes_text_json_and_renders(tmp_path: Path, monkeypatch) -> None:
    sample = BakeoffSample(
        doc_id="doc:010",
        csv_row_id="010",
        source_path=str(tmp_path / "sample.hwp"),
        source_suffix=".hwp",
        project_name="사업",
        issuer="기관",
        csv_text_length=10,
        prior_parse_status="parsed",
        prior_text_length=100,
        prior_ratio=10.0,
        selection_reasons=["large_text"],
    )
    Path(sample.source_path).write_bytes(b"hwp")

    class FakeDoc:
        page_count = 2

        def extract_text(self) -> str:
            return "본문"

        def to_ir_json(self, *, indent=None) -> str:
            return '{"tables": [], "images": []}'

        def export_pdf(self, output_path: str) -> int:
            Path(output_path).write_bytes(b"%PDF")
            return 4

        def export_svg(self, output_dir: str, prefix: str | None = None) -> list[str]:
            path = Path(output_dir) / f"{prefix}-1.svg"
            path.write_text("<svg></svg>", encoding="utf-8")
            return [str(path)]

        def export_png(self, output_dir: str, *, prefix: str | None = None) -> list[str]:
            path = Path(output_dir) / f"{prefix}-1.png"
            path.write_bytes(b"png")
            return [str(path)]

    class FakeRhwp:
        @staticmethod
        def parse(path: str):
            assert path == sample.source_path
            return FakeDoc()

    result = run_rhwp_backend(
        sample,
        out_dir=tmp_path / "out",
        timeout_seconds=5,
        rhwp_module=FakeRhwp,
    )

    assert result.status == BAKEOFF_OK
    assert result.text_length == len("본문")
    assert result.json_length == len('{"tables": [], "images": []}')
    assert result.rendered_pdf_path is not None
    assert result.rendered_svg_count == 1
    assert result.rendered_png_count == 1
    assert result.page_count == 2
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py::test_run_rhwp_backend_writes_text_json_and_renders -q
```

Expected: FAIL because `run_rhwp_backend` does not exist.

- [ ] **Step 3: Implement `run_rhwp_backend`**

Add `import importlib` at the top of `rfp_rag/parser_bakeoff.py`.

Add this function after `_build_result_from_artifacts()`:

```python
def run_rhwp_backend(
    sample: BakeoffSample,
    *,
    out_dir: Path | str,
    timeout_seconds: int,
    rhwp_module: Any | None = None,
) -> BakeoffResult:
    started = time.perf_counter()
    try:
        module = rhwp_module if rhwp_module is not None else importlib.import_module("rhwp")
    except ImportError:
        return _empty_result(sample, backend="rhwp", status=BAKEOFF_MISSING_DEPENDENCY, error_reason="rhwp not installed")

    backend_dir = Path(out_dir) / "backends" / "rhwp"
    backend_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_doc_stem(sample.doc_id)
    text_path = backend_dir / f"{stem}.txt"
    json_path = backend_dir / f"{stem}.json"
    pdf_path = backend_dir / f"{stem}.pdf"
    render_dir = backend_dir / stem
    render_dir.mkdir(parents=True, exist_ok=True)

    try:
        doc = module.parse(sample.source_path)
        text = _normalize_output(doc.extract_text())
        if not text:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return _empty_result(
                sample,
                backend="rhwp",
                status=BAKEOFF_EMPTY_OUTPUT,
                elapsed_ms=elapsed_ms,
                error_reason="empty output",
            )
        text_path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
        if hasattr(doc, "to_ir_json"):
            json_path.write_text(doc.to_ir_json(indent=2).rstrip("\n") + "\n", encoding="utf-8")
        rendered_pdf_path = None
        if hasattr(doc, "export_pdf"):
            doc.export_pdf(str(pdf_path))
            rendered_pdf_path = pdf_path if pdf_path.is_file() else None
        svg_paths = [Path(path) for path in doc.export_svg(str(render_dir), prefix=stem)] if hasattr(doc, "export_svg") else []
        png_paths = [Path(path) for path in doc.export_png(str(render_dir), prefix=stem)] if hasattr(doc, "export_png") else []
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _empty_result(
            sample,
            backend="rhwp",
            status=BAKEOFF_BACKEND_ERROR,
            elapsed_ms=elapsed_ms,
            error_reason=str(exc),
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return _build_result_from_artifacts(
        sample,
        backend="rhwp",
        elapsed_ms=elapsed_ms,
        text_path=text_path,
        json_path=json_path if json_path.is_file() else None,
        rendered_pdf_path=rendered_pdf_path,
        rendered_svg_paths=svg_paths,
        rendered_png_paths=png_paths,
        page_count=getattr(doc, "page_count", None),
    )
```

- [ ] **Step 4: Wire router to `run_rhwp_backend`**

Change this block in `run_backend_for_sample()`:

```python
if backend == "rhwp":
    return run_optional_import_backend(sample, backend=backend, module_name="rhwp", out_dir=out_dir)
```

to:

```python
if backend == "rhwp":
    return run_rhwp_backend(sample, out_dir=out_dir, timeout_seconds=timeout_seconds)
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py::test_run_rhwp_backend_writes_text_json_and_renders -q
```

Expected: PASS.

## Task 4: unhwp Backend Adapter

**Files:**
- Modify: `rfp_rag/parser_bakeoff.py`
- Test: `tests/test_parser_bakeoff.py`

- [ ] **Step 1: Write failing command-routing test**

Add this test:

```python
def test_run_unhwp_backend_uses_markdown_text_and_json_subcommands(tmp_path: Path, monkeypatch) -> None:
    sample = BakeoffSample(
        doc_id="doc:011",
        csv_row_id="011",
        source_path=str(tmp_path / "sample.hwp"),
        source_suffix=".hwp",
        project_name="사업",
        issuer="기관",
        csv_text_length=10,
        prior_parse_status="parsed",
        prior_text_length=100,
        prior_ratio=10.0,
        selection_reasons=["large_text"],
    )
    Path(sample.source_path).write_bytes(b"hwp")
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[1] == "markdown":
            return subprocess.CompletedProcess(command, 0, stdout="# 제목\n\n| A | B |\n|---|---|\n| 1 | 2 |", stderr="")
        if command[1] == "text":
            return subprocess.CompletedProcess(command, 0, stdout="제목\n1 2", stderr="")
        if command[1] == "json":
            return subprocess.CompletedProcess(command, 0, stdout='{"tables": [{"rows": []}], "images": []}', stderr="")
        return subprocess.CompletedProcess(command, 2, stdout="", stderr="bad")

    from rfp_rag import parser_bakeoff

    monkeypatch.setattr(parser_bakeoff, "_find_executable", lambda name, extra_candidates=(): "/tmp/unhwp")

    result = run_unhwp_backend(
        sample,
        out_dir=tmp_path / "out",
        timeout_seconds=5,
        runner=fake_run,
    )

    assert result.status == BAKEOFF_OK
    assert calls == [
        ["/tmp/unhwp", "markdown", sample.source_path],
        ["/tmp/unhwp", "text", sample.source_path],
        ["/tmp/unhwp", "json", sample.source_path],
    ]
    assert result.markdown_length > 0
    assert result.text_length > 0
    assert result.json_length > 0
    assert result.table_count >= 1
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py::test_run_unhwp_backend_uses_markdown_text_and_json_subcommands -q
```

Expected: FAIL because `run_unhwp_backend` does not exist.

- [ ] **Step 3: Implement `run_unhwp_backend`**

Add this function after `run_rhwp_backend()`:

```python
def run_unhwp_backend(
    sample: BakeoffSample,
    *,
    out_dir: Path | str,
    timeout_seconds: int,
    runner: Runner = subprocess.run,
) -> BakeoffResult:
    executable = _find_executable("unhwp", extra_candidates=[Path.home() / ".cargo" / "bin" / "unhwp"])
    if executable is None:
        return _empty_result(sample, backend="unhwp", status=BAKEOFF_MISSING_DEPENDENCY, error_reason="unhwp not found")

    started = time.perf_counter()
    outputs: dict[str, str] = {}
    stderr_parts: list[str] = []
    try:
        for kind, subcommand in [("markdown", "markdown"), ("text", "text"), ("json", "json")]:
            completed = runner(
                [executable, subcommand, sample.source_path],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            stderr_parts.append(_stringify(completed.stderr))
            if completed.returncode != 0:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                return _empty_result(
                    sample,
                    backend="unhwp",
                    status=BAKEOFF_BACKEND_ERROR,
                    elapsed_ms=elapsed_ms,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                    error_reason=f"unhwp {subcommand} exited {completed.returncode}",
                )
            outputs[kind] = _normalize_output(completed.stdout)
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _empty_result(
            sample,
            backend="unhwp",
            status=BAKEOFF_TIMEOUT,
            elapsed_ms=elapsed_ms,
            stdout=exc.stdout or exc.output,
            stderr=exc.stderr,
            error_reason=f"backend timeout after {timeout_seconds}s",
        )

    if not outputs.get("markdown") and not outputs.get("text"):
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _empty_result(
            sample,
            backend="unhwp",
            status=BAKEOFF_EMPTY_OUTPUT,
            elapsed_ms=elapsed_ms,
            error_reason="empty output",
        )

    backend_dir = Path(out_dir) / "backends" / "unhwp"
    backend_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_doc_stem(sample.doc_id)
    markdown_path = backend_dir / f"{stem}.md"
    text_path = backend_dir / f"{stem}.txt"
    json_path = backend_dir / f"{stem}.json"
    markdown_path.write_text(outputs.get("markdown", "").rstrip("\n") + "\n", encoding="utf-8")
    text_path.write_text(outputs.get("text", "").rstrip("\n") + "\n", encoding="utf-8")
    if outputs.get("json"):
        json_path.write_text(outputs["json"].rstrip("\n") + "\n", encoding="utf-8")
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return _build_result_from_artifacts(
        sample,
        backend="unhwp",
        elapsed_ms=elapsed_ms,
        text_path=text_path,
        markdown_path=markdown_path,
        json_path=json_path if json_path.is_file() else None,
        stderr="\n".join(stderr_parts),
    )
```

- [ ] **Step 4: Wire router to `run_unhwp_backend`**

Replace the current `unhwp` block in `run_backend_for_sample()` with:

```python
if backend == "unhwp":
    return run_unhwp_backend(sample, out_dir=out_dir, timeout_seconds=timeout_seconds)
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py::test_run_unhwp_backend_uses_markdown_text_and_json_subcommands -q
```

Expected: PASS.

## Task 5: LibreOffice PDF Adapter

**Files:**
- Modify: `rfp_rag/parser_bakeoff.py`
- Test: `tests/test_parser_bakeoff.py`

- [ ] **Step 1: Write failing LibreOffice adapter test**

Add this test:

```python
def test_run_libreoffice_pdf_backend_records_converted_pdf(tmp_path: Path, monkeypatch) -> None:
    sample = BakeoffSample(
        doc_id="doc:012",
        csv_row_id="012",
        source_path=str(tmp_path / "sample.hwp"),
        source_suffix=".hwp",
        project_name="사업",
        issuer="기관",
        csv_text_length=10,
        prior_parse_status="parsed",
        prior_text_length=100,
        prior_ratio=10.0,
        selection_reasons=["large_text"],
    )
    Path(sample.source_path).write_bytes(b"hwp")

    from rfp_rag import parser_bakeoff

    monkeypatch.setattr(parser_bakeoff, "_find_executable", lambda name, extra_candidates=(): "/Applications/LibreOffice.app/Contents/MacOS/soffice")

    def fake_run(command, **kwargs):
        out_index = command.index("--outdir") + 1
        out_dir = Path(command[out_index])
        (out_dir / "sample.pdf").write_bytes(b"%PDF")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = run_libreoffice_pdf_backend(
        sample,
        out_dir=tmp_path / "out",
        timeout_seconds=5,
        runner=fake_run,
    )

    assert result.status == BAKEOFF_OK
    assert result.rendered_pdf_path is not None
    assert Path(result.rendered_pdf_path).name == "doc_012.pdf"
```

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py::test_run_libreoffice_pdf_backend_records_converted_pdf -q
```

Expected: FAIL because `run_libreoffice_pdf_backend` does not exist.

- [ ] **Step 3: Implement `run_libreoffice_pdf_backend`**

Add this function after `run_unhwp_backend()`:

```python
def run_libreoffice_pdf_backend(
    sample: BakeoffSample,
    *,
    out_dir: Path | str,
    timeout_seconds: int,
    runner: Runner = subprocess.run,
) -> BakeoffResult:
    soffice = _find_executable(
        "soffice",
        extra_candidates=[
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            "/Applications/LibreOffice.app/Contents/MacOS/libreoffice",
        ],
    )
    if soffice is None:
        return _empty_result(
            sample,
            backend="libreoffice_pdf",
            status=BAKEOFF_MISSING_DEPENDENCY,
            error_reason="soffice not found",
        )

    started = time.perf_counter()
    backend_dir = Path(out_dir) / "backends" / "libreoffice_pdf"
    work_dir = backend_dir / _safe_doc_stem(sample.doc_id)
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        completed = runner(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(work_dir), sample.source_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _empty_result(
            sample,
            backend="libreoffice_pdf",
            status=BAKEOFF_TIMEOUT,
            elapsed_ms=elapsed_ms,
            stdout=exc.stdout or exc.output,
            stderr=exc.stderr,
            error_reason=f"backend timeout after {timeout_seconds}s",
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if completed.returncode != 0:
        return _empty_result(
            sample,
            backend="libreoffice_pdf",
            status=BAKEOFF_BACKEND_ERROR,
            elapsed_ms=elapsed_ms,
            stdout=completed.stdout,
            stderr=completed.stderr,
            error_reason=f"soffice exited {completed.returncode}",
        )
    converted = work_dir / f"{Path(sample.source_path).stem}.pdf"
    if not converted.is_file():
        return _empty_result(
            sample,
            backend="libreoffice_pdf",
            status=BAKEOFF_EMPTY_OUTPUT,
            elapsed_ms=elapsed_ms,
            stdout=completed.stdout,
            stderr=completed.stderr,
            error_reason="converted pdf not found",
        )
    final_pdf = backend_dir / f"{_safe_doc_stem(sample.doc_id)}.pdf"
    converted.replace(final_pdf)
    return _build_result_from_artifacts(
        sample,
        backend="libreoffice_pdf",
        elapsed_ms=elapsed_ms,
        rendered_pdf_path=final_pdf,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
```

- [ ] **Step 4: Wire router**

Replace the current `libreoffice_pdf` block with:

```python
if backend == "libreoffice_pdf":
    return run_libreoffice_pdf_backend(sample, out_dir=out_dir, timeout_seconds=timeout_seconds)
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py::test_run_libreoffice_pdf_backend_records_converted_pdf -q
```

Expected: PASS.

## Task 6: hwpkit Optional Candidate

**Files:**
- Modify: `rfp_rag/parser_bakeoff.py`
- Modify: `rfp_rag/run_parser_bakeoff.py`
- Test: `tests/test_parser_bakeoff.py`

- [ ] **Step 1: Add failing optional backend routing test**

Add this test:

```python
def test_run_backend_for_sample_routes_hwpkit_as_optional_hwp_backend(tmp_path: Path) -> None:
    sample = BakeoffSample(
        doc_id="doc:013",
        csv_row_id="013",
        source_path=str(tmp_path / "sample.hwp"),
        source_suffix=".hwp",
        project_name="사업",
        issuer="기관",
        csv_text_length=10,
        prior_parse_status="parsed",
        prior_text_length=100,
        prior_ratio=10.0,
        selection_reasons=["large_text"],
    )

    result = run_backend_for_sample(sample, backend="hwpkit", out_dir=tmp_path / "out", timeout_seconds=5)

    assert result.status in {BAKEOFF_MISSING_DEPENDENCY, BAKEOFF_BACKEND_ERROR}
    assert result.backend == "hwpkit"
```

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py::test_run_backend_for_sample_routes_hwpkit_as_optional_hwp_backend -q
```

Expected: FAIL because `hwpkit` is unknown.

- [ ] **Step 3: Add `hwpkit` suffix and optional routing**

Change the HWP/HWPX optional suffix guard in `run_backend_for_sample()` from:

```python
if backend in {"rhwp", "unhwp", "hwpxkit"} and suffix not in {".hwp", ".hwpx"}:
```

to:

```python
if backend in {"rhwp", "unhwp", "hwpxkit", "hwpkit"} and suffix not in {".hwp", ".hwpx"}:
```

Add this block after `hwpxkit`:

```python
if backend == "hwpkit":
    return run_optional_import_backend(sample, backend=backend, module_name="hwpkit", out_dir=out_dir)
```

In `rfp_rag/run_parser_bakeoff.py`, change `DEFAULT_BACKENDS` to:

```python
DEFAULT_BACKENDS = ["hwp5txt", "hwp5html", "hwp5odt", "rhwp", "unhwp", "hwpxkit", "hwpkit", "libreoffice_pdf"]
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py::test_run_backend_for_sample_routes_hwpkit_as_optional_hwp_backend -q
```

Expected: PASS.

## Task 7: Regression, Smoke, and Docs

**Files:**
- Modify: `REPORT.md`

- [ ] **Step 1: Run focused parser bakeoff tests**

Run:

```bash
uv run --group dev python -m pytest tests/test_parser_bakeoff.py tests/test_parser_bakeoff_cli.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run non-real test suite**

Run:

```bash
uv run --group dev python -m pytest -m "not real" -q
```

Expected: all non-real tests pass.

- [ ] **Step 3: Run a small local bakeoff smoke**

Run:

```bash
uv run --group dev python -m rfp_rag.run_parser_bakeoff \
  --data data/data_list.csv \
  --files data/files \
  --parse-manifest artifacts/parsed_docs/manifest.jsonl \
  --out artifacts/parser_bakeoff \
  --backend rhwp \
  --backend unhwp \
  --backend libreoffice_pdf \
  --hwp-limit 2 \
  --timeout-seconds 30 \
  --no-pdfs
```

Expected: command exits 0 and writes `artifacts/parser_bakeoff/summary.json`.

- [ ] **Step 4: Update `REPORT.md`**

Add a short parser bakeoff update with:

```markdown
### Parser/render backend expansion

The parser/render bakeoff can now measure installed HWP/HWPX and rendering
candidates instead of only recording dependency stubs:

- `rhwp`: extracts text and IR JSON, and records PDF/SVG/PNG render artifacts
  when the installed package supports them.
- `unhwp`: runs Markdown, text, and JSON subcommands through the local CLI,
  including `~/.cargo/bin/unhwp`.
- `libreoffice_pdf`: detects `/Applications/LibreOffice.app/.../soffice` as a
  headless HWP-to-PDF rendering fallback.
- `hwpkit`: tracked as an optional candidate until a real adapter is validated.

Generated bakeoff artifacts remain under ignored `artifacts/parser_bakeoff/`.
```

- [ ] **Step 5: Commit implementation**

Run:

```bash
git add rfp_rag/parser_bakeoff.py rfp_rag/run_parser_bakeoff.py tests/test_parser_bakeoff.py tests/test_parser_bakeoff_cli.py REPORT.md
git commit -m "feat: expand parser bakeoff backends"
```

Expected: commit succeeds without staging unrelated `pyproject.toml` or `uv.lock` unless the implementation intentionally changes dependencies.

## Self-Review

- Spec coverage: implements the near-term parser bakeoff expansion from the A-to-Z design.
- Scope: does not alter indexing, generation, UI, FastMCP, or agent behavior.
- Dependency policy: uses installed `rhwp`, local `unhwp`, and app-bundle LibreOffice; optional packages remain controlled candidates.
- Verification: includes focused tests, full non-real tests, and a local smoke command.
