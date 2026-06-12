# Source Parsing Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce parse artifacts and EDA for original RFP source files under `data/files` without replacing the existing CSV-first corpus path.

**Architecture:** Add a focused `rfp_rag.source_parsing` module for parser backends, manifest records, text-file writing, and summary aggregation. Add a thin `rfp_rag.parse_sources` CLI that loads the existing CSV corpus metadata, runs the parser lane for every row, writes `manifest.jsonl`, `summary.json`, and parsed text files, then update docs with the observed parse EDA.

**Tech Stack:** Python 3.11 stdlib, existing `rfp_rag.corpus` loader, external `hwp5txt` CLI for HWP files, pytest with monkeypatched parser runners.

---

## File Structure

- Create `rfp_rag/source_parsing.py`: parser result dataclasses, HWP parser wrapper, per-document record builder, artifact writer, summary aggregation.
- Create `rfp_rag/parse_sources.py`: CLI and importable `parse_sources(...)` function.
- Create `tests/test_source_parsing.py`: unit tests for backend result mapping, manifest shape, summary aggregation, and artifact writing.
- Create `tests/test_parse_sources_cli.py`: CLI-level tests using a fake parser so tests do not require `hwp5txt`.
- Modify `README.md`: add parse source command and state that CSV remains default.
- Modify `REPORT.md`: add source parsing EDA section after smoke artifacts are produced.

Out of scope for this PR:

- `build_index --source ...`
- PDF parser dependency
- section-aware chunking
- replacing CSV text as default corpus text

---

### Task 1: Source Parsing Core

**Files:**
- Create: `rfp_rag/source_parsing.py`
- Test: `tests/test_source_parsing.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_source_parsing.py`:

```python
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
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="  본문\\n", stderr="warning")

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
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=" \\n ", stderr="")

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
    assert Path(record["text_path"]).read_text(encoding="utf-8") == "원문 본문입니다\\n"


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --group dev python -m pytest tests/test_source_parsing.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'rfp_rag.source_parsing'`.

- [ ] **Step 3: Implement source parsing core**

Create `rfp_rag/source_parsing.py`:

```python
from __future__ import annotations

import json
import statistics
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from .corpus import CorpusDocument

PARSE_PARSED = "parsed"
PARSE_EMPTY_TEXT = "empty_text"
PARSE_UNSUPPORTED_SUFFIX = "unsupported_suffix"
PARSE_MISSING_SOURCE_FILE = "missing_source_file"
PARSE_PARSER_ERROR = "parser_error"
PARSE_TIMEOUT = "timeout"

_STDERR_SAMPLE_LIMIT = 500


@dataclass(frozen=True)
class ParseResult:
    status: str
    parser_backend: str | None
    text: str
    stderr: str
    error_reason: str | None


Runner = Callable[..., subprocess.CompletedProcess[str]]


def safe_doc_filename(doc_id: str) -> str:
    return f"{doc_id.replace(':', '_')}.txt"


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _stderr_sample(stderr: str) -> str:
    return stderr[:_STDERR_SAMPLE_LIMIT]


def parse_hwp_file(
    path: Path | str,
    *,
    timeout_seconds: int = 60,
    runner: Runner = subprocess.run,
) -> ParseResult:
    path = Path(path)
    try:
        completed = runner(
            ["hwp5txt", str(path)],
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return ParseResult(
            status=PARSE_TIMEOUT,
            parser_backend="hwp5txt",
            text="",
            stderr="",
            error_reason=f"parser timeout after {timeout_seconds}s",
        )
    if completed.returncode != 0:
        return ParseResult(
            status=PARSE_PARSER_ERROR,
            parser_backend="hwp5txt",
            text=_normalize_text(completed.stdout or ""),
            stderr=completed.stderr or "",
            error_reason=f"hwp5txt exited {completed.returncode}",
        )
    text = _normalize_text(completed.stdout or "")
    if not text:
        return ParseResult(
            status=PARSE_EMPTY_TEXT,
            parser_backend="hwp5txt",
            text="",
            stderr=completed.stderr or "",
            error_reason="empty stdout",
        )
    return ParseResult(
        status=PARSE_PARSED,
        parser_backend="hwp5txt",
        text=text,
        stderr=completed.stderr or "",
        error_reason=None,
    )


def parse_document_source(doc: CorpusDocument, *, timeout_seconds: int = 60) -> ParseResult:
    source_value = doc.metadata.get("resolved_filesystem_path")
    if not source_value:
        return ParseResult(
            status=PARSE_MISSING_SOURCE_FILE,
            parser_backend=None,
            text="",
            stderr="",
            error_reason="missing resolved source file",
        )
    source_path = Path(str(source_value))
    if not source_path.exists():
        return ParseResult(
            status=PARSE_MISSING_SOURCE_FILE,
            parser_backend=None,
            text="",
            stderr="",
            error_reason="missing resolved source file",
        )
    suffix = source_path.suffix.lower()
    if suffix == ".hwp":
        return parse_hwp_file(source_path, timeout_seconds=timeout_seconds)
    return ParseResult(
        status=PARSE_UNSUPPORTED_SUFFIX,
        parser_backend=None,
        text="",
        stderr="",
        error_reason=f"unsupported suffix: {suffix or '<none>'}",
    )


def build_parse_record(doc: CorpusDocument, result: ParseResult, out_dir: Path | str) -> dict[str, Any]:
    out_dir = Path(out_dir)
    source_value = doc.metadata.get("resolved_filesystem_path")
    source_path = Path(str(source_value)) if source_value else None
    text_path: Path | None = None
    if result.status == PARSE_PARSED:
        text_dir = out_dir / "text"
        text_dir.mkdir(parents=True, exist_ok=True)
        text_path = text_dir / safe_doc_filename(doc.doc_id)
        text_path.write_text(result.text + "\n", encoding="utf-8")
    csv_len = len(doc.text or "")
    parsed_len = len(result.text or "")
    ratio = (parsed_len / csv_len) if csv_len and parsed_len else None
    return {
        "doc_id": doc.doc_id,
        "csv_row_id": doc.csv_row_id,
        "source_path": None if source_path is None else str(source_path),
        "source_suffix": "" if source_path is None else source_path.suffix.lower(),
        "parser_backend": result.parser_backend,
        "parse_status": result.status,
        "text_path": None if text_path is None else str(text_path),
        "text_length": parsed_len,
        "stderr_length": len(result.stderr or ""),
        "stderr_sample": _stderr_sample(result.stderr or ""),
        "error_reason": result.error_reason,
        "csv_text_length": csv_len,
        "parsed_to_csv_length_ratio": ratio,
    }


def _distribution(values: Iterable[float | int]) -> dict[str, float | int | None]:
    data = sorted(values)
    if not data:
        return {"min": None, "median": None, "max": None}
    return {"min": data[0], "median": statistics.median(data), "max": data[-1]}


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(str(r.get("parse_status")) for r in records)
    backend_counts = Counter(str(r.get("parser_backend")) for r in records if r.get("parser_backend"))
    suffix_counts = Counter(str(r.get("source_suffix") or "") for r in records)
    error_counts = Counter(str(r.get("error_reason")) for r in records if r.get("error_reason"))
    parsed_count = status_counts.get(PARSE_PARSED, 0)
    row_count = len(records)
    ratios = [r["parsed_to_csv_length_ratio"] for r in records if r.get("parsed_to_csv_length_ratio") is not None]
    return {
        "row_count": row_count,
        "suffix_counts": dict(sorted(suffix_counts.items())),
        "parse_status_counts": dict(sorted(status_counts.items())),
        "parser_backend_counts": dict(sorted(backend_counts.items())),
        "parsed_success_rate": parsed_count / row_count if row_count else 0.0,
        "empty_parse_count": status_counts.get(PARSE_EMPTY_TEXT, 0),
        "text_length": _distribution(int(r.get("text_length") or 0) for r in records),
        "csv_text_length": _distribution(int(r.get("csv_text_length") or 0) for r in records),
        "parsed_to_csv_length_ratio": _distribution(ratios),
        "top_error_reasons": dict(error_counts.most_common(10)),
    }


def write_parse_artifacts(records: list[dict[str, Any]], out_dir: Path | str) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    summary = summarize_records(records)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --group dev python -m pytest tests/test_source_parsing.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/source_parsing.py tests/test_source_parsing.py
git commit -m "feat: add source parsing core"
```

---

### Task 2: Parse Sources CLI

**Files:**
- Create: `rfp_rag/parse_sources.py`
- Test: `tests/test_parse_sources_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_parse_sources_cli.py`:

```python
from __future__ import annotations

import csv
import json
from pathlib import Path

from rfp_rag import parse_sources as parse_sources_module
from rfp_rag.parse_sources import main, parse_sources
from rfp_rag.source_parsing import PARSE_PARSED, PARSE_UNSUPPORTED_SUFFIX, ParseResult


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


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _row(filename: str, text: str = "CSV 본문") -> dict[str, str]:
    return {
        "공고 번호": "1",
        "공고 차수": "0",
        "사업명": "테스트 사업",
        "사업 금액": "1000",
        "발주 기관": "테스트기관",
        "공개 일자": "",
        "입찰 참여 시작일": "",
        "입찰 참여 마감일": "",
        "사업 요약": "요약",
        "파일형식": Path(filename).suffix.lstrip("."),
        "파일명": filename,
        "텍스트": text,
    }


def test_parse_sources_writes_manifest_summary_and_text(tmp_path: Path, monkeypatch) -> None:
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    (files_dir / "a.hwp").write_bytes(b"hwp")
    (files_dir / "b.pdf").write_bytes(b"pdf")
    csv_path = tmp_path / "data.csv"
    _write_csv(csv_path, [_row("a.hwp"), _row("b.pdf")])

    def fake_parse_document_source(doc, *, timeout_seconds: int = 60):
        if doc.metadata["csv_filename_raw"] == "a.hwp":
            return ParseResult(PARSE_PARSED, "hwp5txt", "원문 본문", "warn", None)
        return ParseResult(PARSE_UNSUPPORTED_SUFFIX, None, "", "", "unsupported suffix: .pdf")

    monkeypatch.setattr(parse_sources_module, "parse_document_source", fake_parse_document_source)

    summary = parse_sources(csv_path, files_dir, tmp_path / "parsed", timeout_seconds=7)

    manifest_lines = (tmp_path / "parsed" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in manifest_lines]
    assert summary["row_count"] == 2
    assert summary["parse_status_counts"] == {PARSE_PARSED: 1, PARSE_UNSUPPORTED_SUFFIX: 1}
    assert records[0]["parse_status"] == PARSE_PARSED
    assert records[0]["text_path"].endswith("doc_000.txt")
    assert (tmp_path / "parsed" / "text" / "doc_000.txt").read_text(encoding="utf-8") == "원문 본문\\n"
    assert records[1]["parse_status"] == PARSE_UNSUPPORTED_SUFFIX
    assert json.loads((tmp_path / "parsed" / "summary.json").read_text(encoding="utf-8")) == summary


def test_main_prints_summary_json(tmp_path: Path, monkeypatch, capsys) -> None:
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    (files_dir / "a.hwp").write_bytes(b"hwp")
    csv_path = tmp_path / "data.csv"
    _write_csv(csv_path, [_row("a.hwp")])

    def fake_parse_document_source(doc, *, timeout_seconds: int = 60):
        return ParseResult(PARSE_PARSED, "hwp5txt", "원문", "", None)

    monkeypatch.setattr(parse_sources_module, "parse_document_source", fake_parse_document_source)

    rc = main([
        "--data", str(csv_path),
        "--files", str(files_dir),
        "--out", str(tmp_path / "parsed"),
        "--timeout-seconds", "3",
    ])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["row_count"] == 1
    assert payload["parse_status_counts"] == {PARSE_PARSED: 1}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --group dev python -m pytest tests/test_parse_sources_cli.py -q
```

Expected: FAIL with `ModuleNotFoundError` or import error for `rfp_rag.parse_sources`.

- [ ] **Step 3: Implement CLI**

Create `rfp_rag/parse_sources.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .corpus import load_corpus
from .source_parsing import build_parse_record, parse_document_source, write_parse_artifacts


def parse_sources(
    data_path: Path | str,
    files_path: Path | str,
    out_dir: Path | str,
    *,
    timeout_seconds: int = 60,
) -> dict[str, object]:
    docs = load_corpus(data_path, files_path)
    out_dir = Path(out_dir)
    records = []
    for doc in docs:
        result = parse_document_source(doc, timeout_seconds=timeout_seconds)
        records.append(build_parse_record(doc, result, out_dir))
    return write_parse_artifacts(records, out_dir)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse original RFP source files into local text artifacts.")
    parser.add_argument("--data", required=True, type=Path, help="Path to data_list.csv")
    parser.add_argument("--files", required=True, type=Path, help="Path to source file directory")
    parser.add_argument("--out", required=True, type=Path, help="Parsed artifact output directory")
    parser.add_argument("--timeout-seconds", default=60, type=int, help="Per-document parser timeout")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    summary = parse_sources(
        args.data,
        args.files,
        args.out,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run --group dev python -m pytest tests/test_parse_sources_cli.py tests/test_source_parsing.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/parse_sources.py tests/test_parse_sources_cli.py
git commit -m "feat: add parse sources CLI"
```

---

### Task 3: Parser Smoke and Documentation

**Files:**
- Modify: `README.md`
- Modify: `REPORT.md`

- [ ] **Step 1: Run focused parser tests**

Run:

```bash
uv run --group dev python -m pytest tests/test_source_parsing.py tests/test_parse_sources_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run source parser smoke on real dataset**

Run:

```bash
uv run --group dev python -m rfp_rag.parse_sources \
  --data data/data_list.csv \
  --files data/files \
  --out artifacts/parsed_docs
```

Expected: command exits `0`, writes `artifacts/parsed_docs/manifest.jsonl`, `summary.json`, and text files for successfully parsed HWP documents.

- [ ] **Step 3: Extract summary values**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path("artifacts/parsed_docs/summary.json").read_text(encoding="utf-8"))
print(json.dumps({
    "row_count": summary["row_count"],
    "suffix_counts": summary["suffix_counts"],
    "parse_status_counts": summary["parse_status_counts"],
    "parser_backend_counts": summary["parser_backend_counts"],
    "parsed_success_rate": summary["parsed_success_rate"],
    "empty_parse_count": summary["empty_parse_count"],
    "text_length": summary["text_length"],
    "csv_text_length": summary["csv_text_length"],
    "parsed_to_csv_length_ratio": summary["parsed_to_csv_length_ratio"],
    "top_error_reasons": summary["top_error_reasons"],
}, ensure_ascii=False, indent=2))
PY
```

Expected: JSON summary with 100 rows and controlled statuses.

- [ ] **Step 4: Update README**

Add this section after the base command block:

```markdown
## Source parsing lane

The current RAG path remains CSV-first. Source parsing is a separate artifact lane that extracts original HWP/PDF source text and records parser quality before parsed text is used for indexing.

```bash
python3 -m rfp_rag.parse_sources --data data/data_list.csv --files data/files --out artifacts/parsed_docs
```

Outputs:

- `artifacts/parsed_docs/manifest.jsonl`
- `artifacts/parsed_docs/summary.json`
- `artifacts/parsed_docs/text/*.txt` for parsed documents

The first implementation uses local `hwp5txt` for `.hwp` files and records `.pdf` files as unsupported unless a PDF backend is added later.
```

- [ ] **Step 5: Update REPORT with actual parser EDA**

Run this helper to generate the Markdown table for the REPORT section:

```bash
python3 - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path("artifacts/parsed_docs/summary.json").read_text(encoding="utf-8"))
rows = [
    ("row_count", summary["row_count"]),
    ("suffix_counts", summary["suffix_counts"]),
    ("parse_status_counts", summary["parse_status_counts"]),
    ("parser_backend_counts", summary["parser_backend_counts"]),
    ("parsed_success_rate", summary["parsed_success_rate"]),
    ("empty_parse_count", summary["empty_parse_count"]),
    ("text_length", summary["text_length"]),
    ("csv_text_length", summary["csv_text_length"]),
    ("parsed_to_csv_length_ratio", summary["parsed_to_csv_length_ratio"]),
    ("top_error_reasons", summary["top_error_reasons"]),
]
print("| metric | value |")
print("|---|---|")
for key, value in rows:
    print(f"| {key} | `{json.dumps(value, ensure_ascii=False, sort_keys=True)}` |")
PY
```

Add this section before `## 11. 결론`, placing the generated table between the opening paragraph and `재현 커맨드:`:

```markdown
### 10-17. Source Parsing Lane

현재 RAG index는 CSV `텍스트` 컬럼을 기준으로 한다. 원문 파싱 lane은 기존 baseline을 대체하지 않고, `data/files`의 원본 HWP/PDF 파싱 품질을 먼저 계측한다.

재현 커맨드:

```bash
python3 -m rfp_rag.parse_sources --data data/data_list.csv --files data/files --out artifacts/parsed_docs
```

해석:

- CSV baseline은 유지한다.
- HWP는 `hwp5txt`로 파싱한다.
- PDF는 첫 구현에서 unsupported로 기록한다.
- source-aware indexing은 parser EDA 확인 후 별도 PR에서 `--source csv|parsed|parsed-with-csv-fallback`로 추가한다.
```

The committed `REPORT.md` section must contain the generated table, not the generator command output instructions.

- [ ] **Step 6: Run docs checks**

Run:

```bash
uv run --group dev python -m rfp_rag.report_check --eval artifacts/eval --readme README.md
rg -n "Source parsing lane|parse_sources|parsed_docs|10-17" README.md REPORT.md
```

Expected: report check returns `"ok": true`; ripgrep finds the new source parsing docs.

- [ ] **Step 7: Commit docs**

```bash
git add README.md REPORT.md
git commit -m "docs: record source parsing smoke"
```

---

### Task 4: Final Verification and PR

**Files:**
- No source edits expected.

- [ ] **Step 1: Run full credential-free tests**

Run:

```bash
uv run --group dev python -m pytest -m "not real" -q
```

Expected: PASS.

- [ ] **Step 2: Verify parser artifacts still exist locally**

Run:

```bash
test -s artifacts/parsed_docs/manifest.jsonl
test -s artifacts/parsed_docs/summary.json
python3 - <<'PY'
import json
from pathlib import Path
summary = json.loads(Path("artifacts/parsed_docs/summary.json").read_text(encoding="utf-8"))
assert summary["row_count"] == 100
print(json.dumps({
    "row_count": summary["row_count"],
    "parse_status_counts": summary["parse_status_counts"],
    "parsed_success_rate": summary["parsed_success_rate"],
}, ensure_ascii=False, sort_keys=True))
PY
```

Expected: commands exit `0` and print a compact parser summary.

- [ ] **Step 3: Check git status and ignored artifacts**

Run:

```bash
git status --short --ignored
```

Expected: source/docs/test files are clean; `artifacts/` remains ignored and is not committed.

- [ ] **Step 4: Push branch**

Run:

```bash
git push -u origin feature/source-parsing-lane
```

Expected: branch pushed or updated.

- [ ] **Step 5: Open draft PR**

Run:

```bash
gh pr create --draft --base master --head feature/source-parsing-lane \
  --title "[codex] Add source parsing lane" \
  --body "## Summary
- add source parser artifacts for original RFP files
- parse HWP files with hwp5txt and record unsupported PDF rows explicitly
- document source parsing EDA while keeping CSV as the default RAG source

## Test Plan
- uv run --group dev python -m pytest -m \"not real\" -q
- uv run --group dev python -m rfp_rag.parse_sources --data data/data_list.csv --files data/files --out artifacts/parsed_docs
- uv run --group dev python -m rfp_rag.report_check --eval artifacts/eval --readme README.md"
```

Expected: draft PR URL.

---

## Self-Review

- Spec coverage: parser backend mapping, manifest shape, CLI artifacts, summary aggregation, docs, smoke run, and CSV baseline preservation are covered.
- Scope check: source-aware indexing is intentionally excluded and documented as the next PR.
- Completion-value scan: committed docs must use values generated from `summary.json`; Task 3 generates the REPORT table before commit.
- Type consistency: `ParseResult`, parse status constants, `parse_sources(...)`, and artifact paths are named consistently across tasks.
