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
            writer.writerow(
                {
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
                }
            )


def _write_manifest(path: Path, filenames: list[str]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for idx, filename in enumerate(filenames):
            suffix = Path(filename).suffix.lower()
            f.write(
                json.dumps(
                    {
                        "doc_id": f"doc:{idx:03d}",
                        "source_path": str(path.parent / "files" / filename),
                        "source_suffix": suffix,
                        "parse_status": "parsed" if suffix == ".hwp" else "unsupported_suffix",
                        "text_length": 1000 + idx,
                        "csv_text_length": 100,
                        "parsed_to_csv_length_ratio": 10.0 + idx,
                        "error_reason": None,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def _fake_result(sample, *, backend: str) -> BakeoffResult:
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
        return _fake_result(sample, backend=backend)

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
        return _fake_result(sample, backend=backend)

    monkeypatch.setattr(cli_module, "run_backend_for_sample", fake_run_backend_for_sample)

    rc = main(
        [
            "--data",
            str(csv_path),
            "--files",
            str(files_dir),
            "--parse-manifest",
            str(manifest_path),
            "--out",
            str(tmp_path / "out"),
            "--backend",
            "fake",
            "--hwp-limit",
            "1",
            "--timeout-seconds",
            "2",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["result_count"] == 1
    assert payload["backend_counts"] == {"fake": 1}
