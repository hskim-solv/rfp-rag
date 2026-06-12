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
    assert (tmp_path / "parsed" / "text" / "doc_000.txt").read_text(encoding="utf-8") == "원문 본문\n"
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

    rc = main(
        [
            "--data",
            str(csv_path),
            "--files",
            str(files_dir),
            "--out",
            str(tmp_path / "parsed"),
            "--timeout-seconds",
            "3",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["row_count"] == 1
    assert payload["parse_status_counts"] == {PARSE_PARSED: 1}
