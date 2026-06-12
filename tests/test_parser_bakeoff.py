from __future__ import annotations

import json
import subprocess
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
    run_optional_import_backend,
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
