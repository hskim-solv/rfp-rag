from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

from rfp_rag.corpus import CorpusDocument
from rfp_rag.parser_bakeoff import (
    BAKEOFF_BACKEND_ERROR,
    BAKEOFF_EMPTY_OUTPUT,
    BAKEOFF_MISSING_DEPENDENCY,
    BAKEOFF_OK,
    BAKEOFF_TIMEOUT,
    BAKEOFF_UNSUPPORTED_FORMAT,
    BakeoffResult,
    BakeoffSample,
    run_backend_for_sample,
    run_command_backend,
    run_libreoffice_pdf_backend,
    run_optional_import_backend,
    run_rhwp_backend,
    run_unhwp_backend,
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


def test_bakeoff_status_constants_are_exact() -> None:
    assert {
        BAKEOFF_BACKEND_ERROR,
        BAKEOFF_EMPTY_OUTPUT,
        BAKEOFF_MISSING_DEPENDENCY,
        BAKEOFF_OK,
        BAKEOFF_TIMEOUT,
        BAKEOFF_UNSUPPORTED_FORMAT,
    } == {
        "backend_error",
        "empty_output",
        "missing_dependency",
        "ok",
        "timeout",
        "unsupported_format",
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


def test_summarize_bakeoff_results_recommends_fallbacks_for_failed_rhwp() -> None:
    def result(
        *,
        backend: str,
        status: str,
        text_length: int = 0,
        rendered_pdf_path: str | None = None,
        error_reason: str | None = None,
    ) -> BakeoffResult:
        return BakeoffResult(
            doc_id="doc:042",
            source_path="broken-docinfo.hwp",
            source_suffix=".hwp",
            backend=backend,
            status=status,
            elapsed_ms=1,
            text_path="out.txt" if text_length else None,
            markdown_path=None,
            html_path=None,
            json_path=None,
            rendered_pdf_path=rendered_pdf_path,
            rendered_svg_count=0,
            rendered_png_count=0,
            asset_count=0,
            text_length=text_length,
            markdown_length=0,
            html_length=0,
            json_length=0,
            table_count=0,
            image_count=0,
            page_count=None,
            stdout_length=0,
            stderr_length=0,
            error_reason=error_reason,
        )

    summary = summarize_bakeoff_results(
        [
            result(
                backend="rhwp",
                status=BAKEOFF_BACKEND_ERROR,
                error_reason="DocInfo UTF-16 decode failed",
            ),
            result(backend="unhwp", status=BAKEOFF_OK, text_length=63786),
            result(
                backend="libreoffice_pdf",
                status=BAKEOFF_OK,
                rendered_pdf_path="artifacts/parser_bakeoff/backends/libreoffice_pdf/doc_042.pdf",
            ),
        ]
    )

    assert summary["fallback_recommendations"] == [
        {
            "doc_id": "doc:042",
            "failed_backend": "rhwp",
            "failed_error_reason": "DocInfo UTF-16 decode failed",
            "text_fallback_backend": "unhwp",
            "text_fallback_text_length": 63786,
            "visual_fallback_backend": "libreoffice_pdf",
            "visual_fallback_rendered_pdf_path": "artifacts/parser_bakeoff/backends/libreoffice_pdf/doc_042.pdf",
        }
    ]


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
    assert json.loads((tmp_path / "bakeoff" / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])[
        "backend"
    ] == "hwp5txt"
    assert json.loads((tmp_path / "bakeoff" / "summary.json").read_text(encoding="utf-8")) == summary


def test_run_command_backend_writes_text_output(tmp_path: Path) -> None:
    source = tmp_path / "sample.hwp"
    source.write_bytes(b"hwp")
    sample = BakeoffSample(
        doc_id="doc:000",
        csv_row_id="000",
        source_path=str(source),
        source_suffix=".hwp",
        project_name="사업",
        issuer="기관",
        csv_text_length=10,
        prior_parse_status="parsed",
        prior_text_length=100,
        prior_ratio=10.0,
        selection_reasons=["large_text"],
    )

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=" 본문\n", stderr="warn")

    result = run_command_backend(
        sample,
        backend="hwp5txt",
        command=["hwp5txt", str(source)],
        out_dir=tmp_path / "out",
        timeout_seconds=5,
        output_kind="text",
        runner=runner,
    )

    assert result.status == BAKEOFF_OK
    assert result.text_length == len("본문")
    assert result.stderr_length == len("warn")
    assert result.text_path == str(tmp_path / "out" / "backends" / "hwp5txt" / "doc_000.txt")
    assert Path(result.text_path).read_text(encoding="utf-8") == "본문\n"


def test_find_executable_prefers_path_then_extra_candidates(tmp_path: Path, monkeypatch) -> None:
    from rfp_rag import parser_bakeoff

    extra = tmp_path / "tool"
    extra.write_text("#!/bin/sh\n", encoding="utf-8")
    extra.chmod(0o755)

    monkeypatch.setattr(parser_bakeoff.shutil, "which", lambda name: None)

    assert parser_bakeoff._find_executable("missing", extra_candidates=[extra]) == str(extra)
    assert parser_bakeoff._find_executable("missing", extra_candidates=[tmp_path / "absent"]) is None


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


def test_run_rhwp_backend_writes_text_json_and_renders(tmp_path: Path) -> None:
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


def test_run_rhwp_backend_enforces_process_timeout(tmp_path: Path) -> None:
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

    class NeverFinishingProcess:
        exitcode = None
        terminated = False
        killed = False

        def __init__(self, *, target, args) -> None:
            self.target = target
            self.args = args
            self.alive = False

        def start(self) -> None:
            self.alive = True

        def join(self, timeout=None) -> None:
            return None

        def is_alive(self) -> bool:
            return self.alive

        def terminate(self) -> None:
            self.terminated = True
            self.alive = False
            self.exitcode = -15

        def kill(self) -> None:
            self.killed = True
            self.alive = False
            self.exitcode = -9

    class FakeProcessContext:
        def __init__(self) -> None:
            self.process: NeverFinishingProcess | None = None

        def Queue(self):
            return object()

        def Process(self, *, target, args):
            self.process = NeverFinishingProcess(target=target, args=args)
            return self.process

    process_context = FakeProcessContext()

    result = run_rhwp_backend(
        sample,
        out_dir=tmp_path / "out",
        timeout_seconds=3,
        process_context=process_context,
    )

    assert result.status == BAKEOFF_TIMEOUT
    assert result.error_reason == "backend timeout after 3s"
    assert process_context.process is not None
    assert process_context.process.terminated is True


def test_run_rhwp_backend_captures_worker_logs_without_parent_leak(
    tmp_path: Path,
    monkeypatch,
    capfd,
) -> None:
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
        page_count = 1

        def extract_text(self) -> str:
            print("rhwp stdout noise")
            print("rhwp stderr noise", file=sys.stderr)
            os.write(1, b"rhwp fd stdout noise\n")
            os.write(2, b"rhwp fd stderr noise\n")
            return "본문"

    class FakeRhwp:
        @staticmethod
        def parse(path: str):
            assert path == sample.source_path
            return FakeDoc()

    class FakeQueue:
        def __init__(self) -> None:
            self.value = None

        def put(self, value) -> None:
            self.value = value

        def get(self, timeout=None):
            return self.value

    class ImmediateProcess:
        exitcode = None

        def __init__(self, *, target, args) -> None:
            self.target = target
            self.args = args

        def start(self) -> None:
            self.target(*self.args)
            self.exitcode = 0

        def join(self, timeout=None) -> None:
            return None

        def is_alive(self) -> bool:
            return False

    class ImmediateProcessContext:
        def Queue(self):
            return FakeQueue()

        def Process(self, *, target, args):
            return ImmediateProcess(target=target, args=args)

    original_import_module = importlib.import_module
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: FakeRhwp if name == "rhwp" else original_import_module(name),
    )

    result = run_rhwp_backend(
        sample,
        out_dir=tmp_path / "out",
        timeout_seconds=5,
        process_context=ImmediateProcessContext(),
    )

    captured = capfd.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert result.status == BAKEOFF_OK
    assert result.stdout_length == len("rhwp stdout noise\nrhwp fd stdout noise")
    assert result.stderr_length == len("rhwp stderr noise\nrhwp fd stderr noise")


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

    monkeypatch.setattr(
        parser_bakeoff,
        "_find_executable",
        lambda name, extra_candidates=(): "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    )

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


def test_run_command_backend_counts_html_tables_and_images(tmp_path: Path) -> None:
    sample = BakeoffSample(
        doc_id="doc:006",
        csv_row_id="006",
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

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="<html><table></table><TABLE></TABLE><img src='a'></html>",
            stderr="",
        )

    result = run_command_backend(
        sample,
        backend="hwp5html",
        command=["hwp5html", "--html", sample.source_path],
        out_dir=tmp_path / "out",
        timeout_seconds=5,
        output_kind="html",
        runner=runner,
    )

    assert result.status == BAKEOFF_OK
    assert result.html_path == str(tmp_path / "out" / "backends" / "hwp5html" / "doc_006.html")
    assert result.html_length == len("<html><table></table><TABLE></TABLE><img src='a'></html>")
    assert result.table_count == 2
    assert result.image_count == 1


def test_run_command_backend_records_errors_without_files(tmp_path: Path) -> None:
    sample = BakeoffSample(
        doc_id="doc:001",
        csv_row_id="001",
        source_path=str(tmp_path / "sample.hwp"),
        source_suffix=".hwp",
        project_name="사업",
        issuer="기관",
        csv_text_length=10,
        prior_parse_status="parser_error",
        prior_text_length=0,
        prior_ratio=None,
        selection_reasons=["parser_error"],
    )

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=2, stdout="", stderr="boom")

    result = run_command_backend(
        sample,
        backend="hwp5txt",
        command=["hwp5txt", sample.source_path],
        out_dir=tmp_path / "out",
        timeout_seconds=5,
        output_kind="text",
        runner=runner,
    )

    assert result.status == BAKEOFF_BACKEND_ERROR
    assert result.error_reason == "hwp5txt exited 2"
    assert result.text_path is None
    assert result.stderr_length == len("boom")


def test_run_command_backend_records_empty_output(tmp_path: Path) -> None:
    sample = BakeoffSample(
        doc_id="doc:001",
        csv_row_id="001",
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

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=" \n", stderr="")

    result = run_command_backend(
        sample,
        backend="hwp5txt",
        command=["hwp5txt", sample.source_path],
        out_dir=tmp_path / "out",
        timeout_seconds=5,
        output_kind="text",
        runner=runner,
    )

    assert result.status == BAKEOFF_EMPTY_OUTPUT
    assert result.error_reason == "empty output"
    assert result.text_path is None


def test_run_command_backend_records_timeout_and_missing_dependency(tmp_path: Path) -> None:
    sample = BakeoffSample(
        doc_id="doc:002",
        csv_row_id="002",
        source_path=str(tmp_path / "sample.hwp"),
        source_suffix=".hwp",
        project_name="사업",
        issuer="기관",
        csv_text_length=10,
        prior_parse_status="parsed",
        prior_text_length=100,
        prior_ratio=10.0,
        selection_reasons=["median_text"],
    )

    def timeout_runner(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=3, output="partial", stderr="slow")

    timeout_result = run_command_backend(
        sample,
        backend="hwp5txt",
        command=["hwp5txt", sample.source_path],
        out_dir=tmp_path / "out",
        timeout_seconds=3,
        output_kind="text",
        runner=timeout_runner,
    )

    def missing_runner(*args, **kwargs):
        raise FileNotFoundError

    missing_result = run_command_backend(
        sample,
        backend="missing",
        command=["missing", sample.source_path],
        out_dir=tmp_path / "out",
        timeout_seconds=3,
        output_kind="text",
        runner=missing_runner,
    )

    assert timeout_result.status == BAKEOFF_TIMEOUT
    assert timeout_result.error_reason == "backend timeout after 3s"
    assert timeout_result.stdout_length == len("partial")
    assert timeout_result.stderr_length == len("slow")
    assert missing_result.status == BAKEOFF_MISSING_DEPENDENCY
    assert missing_result.error_reason == "missing not found"


def test_run_optional_import_backend_missing_dependency(tmp_path: Path) -> None:
    sample = BakeoffSample(
        doc_id="doc:003",
        csv_row_id="003",
        source_path=str(tmp_path / "sample.hwp"),
        source_suffix=".hwp",
        project_name="사업",
        issuer="기관",
        csv_text_length=10,
        prior_parse_status="parsed",
        prior_text_length=100,
        prior_ratio=10.0,
        selection_reasons=["high_ratio"],
    )

    result = run_optional_import_backend(
        sample,
        backend="rhwp",
        module_name="definitely_missing_rhwp_module",
        out_dir=tmp_path / "out",
    )

    assert result.status == BAKEOFF_MISSING_DEPENDENCY
    assert result.error_reason == "definitely_missing_rhwp_module not installed"


def test_run_backend_for_sample_routes_hwp5txt_and_rejects_pdf(tmp_path: Path, monkeypatch) -> None:
    hwp_sample = BakeoffSample(
        doc_id="doc:004",
        csv_row_id="004",
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
    pdf_sample = BakeoffSample(
        doc_id="doc:005",
        csv_row_id="005",
        source_path=str(tmp_path / "sample.pdf"),
        source_suffix=".pdf",
        project_name="사업",
        issuer="기관",
        csv_text_length=10,
        prior_parse_status="unsupported_suffix",
        prior_text_length=0,
        prior_ratio=None,
        selection_reasons=["pdf_reference"],
    )

    def fake_command(sample, *, backend, command, out_dir, timeout_seconds, output_kind, runner=subprocess.run):
        return BakeoffResult(
            doc_id=sample.doc_id,
            source_path=sample.source_path,
            source_suffix=sample.source_suffix,
            backend=backend,
            status=BAKEOFF_OK,
            elapsed_ms=1,
            text_path="out.txt",
            markdown_path=None,
            html_path=None,
            json_path=None,
            rendered_pdf_path=None,
            rendered_svg_count=0,
            rendered_png_count=0,
            asset_count=0,
            text_length=4,
            markdown_length=0,
            html_length=0,
            json_length=0,
            table_count=0,
            image_count=0,
            page_count=None,
            stdout_length=4,
            stderr_length=0,
            error_reason=None,
        )

    monkeypatch.setattr("rfp_rag.parser_bakeoff.run_command_backend", fake_command)

    hwp_result = run_backend_for_sample(hwp_sample, backend="hwp5txt", out_dir=tmp_path / "out", timeout_seconds=5)
    pdf_result = run_backend_for_sample(pdf_sample, backend="hwp5txt", out_dir=tmp_path / "out", timeout_seconds=5)

    assert hwp_result.status == BAKEOFF_OK
    assert pdf_result.status == BAKEOFF_UNSUPPORTED_FORMAT
    assert pdf_result.error_reason == "hwp5txt supports only .hwp"


def test_run_backend_for_sample_rejects_pdf_for_optional_hwp_backends(tmp_path: Path) -> None:
    pdf_sample = BakeoffSample(
        doc_id="doc:007",
        csv_row_id="007",
        source_path=str(tmp_path / "sample.pdf"),
        source_suffix=".pdf",
        project_name="사업",
        issuer="기관",
        csv_text_length=10,
        prior_parse_status="unsupported_suffix",
        prior_text_length=0,
        prior_ratio=None,
        selection_reasons=["pdf_reference"],
    )

    for backend in ["rhwp", "unhwp", "hwpxkit"]:
        result = run_backend_for_sample(pdf_sample, backend=backend, out_dir=tmp_path / "out", timeout_seconds=5)
        assert result.status == BAKEOFF_UNSUPPORTED_FORMAT
        assert result.error_reason == f"{backend} supports only .hwp/.hwpx"


def test_run_backend_for_sample_routes_hwp5odt_as_xml_text_artifact(tmp_path: Path, monkeypatch) -> None:
    hwp_sample = BakeoffSample(
        doc_id="doc:008",
        csv_row_id="008",
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
    calls: list[dict[str, object]] = []

    def fake_command(sample, *, backend, command, out_dir, timeout_seconds, output_kind, runner=subprocess.run):
        calls.append({"backend": backend, "command": command, "output_kind": output_kind})
        return BakeoffResult(
            doc_id=sample.doc_id,
            source_path=sample.source_path,
            source_suffix=sample.source_suffix,
            backend=backend,
            status=BAKEOFF_OK,
            elapsed_ms=1,
            text_path=str(tmp_path / "out" / "backends" / "hwp5odt" / "doc_008.xml"),
            markdown_path=None,
            html_path=None,
            json_path=None,
            rendered_pdf_path=None,
            rendered_svg_count=0,
            rendered_png_count=0,
            asset_count=0,
            text_length=4,
            markdown_length=0,
            html_length=0,
            json_length=0,
            table_count=0,
            image_count=0,
            page_count=None,
            stdout_length=4,
            stderr_length=0,
            error_reason=None,
        )

    monkeypatch.setattr("rfp_rag.parser_bakeoff.run_command_backend", fake_command)

    result = run_backend_for_sample(hwp_sample, backend="hwp5odt", out_dir=tmp_path / "out", timeout_seconds=5)

    assert result.status == BAKEOFF_OK
    assert calls == [
        {
            "backend": "hwp5odt",
            "command": ["hwp5odt", "--document", hwp_sample.source_path],
            "output_kind": "xml",
        }
    ]
