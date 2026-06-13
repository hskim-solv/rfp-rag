from __future__ import annotations

import csv
import json
import unicodedata
from pathlib import Path

from rfp_rag.corpus import inspect_corpus, load_corpus, resolve_filename_map


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
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
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_load_corpus_pins_row_ids_and_resolves_unicode_filenames(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    nfc_name = "기관_한글제안요청서.hwp"
    nfd_name = unicodedata.normalize("NFD", nfc_name)
    (files_dir / nfd_name).write_text("raw placeholder", encoding="utf-8")
    csv_path = tmp_path / "data.csv"
    _write_csv(
        csv_path,
        [
            {
                "공고 번호": "202400001",
                "공고 차수": "0.0",
                "사업명": "테스트 사업",
                "사업 금액": "130000000.0",
                "발주 기관": "테스트기관",
                "공개 일자": "2024-10-04 13:51:23",
                "입찰 참여 시작일": "",
                "입찰 참여 마감일": "2024-10-15 17:00:00",
                "사업 요약": "요약",
                "파일형식": "hwp",
                "파일명": nfc_name,
                "텍스트": "본문 텍스트",
            }
        ],
    )

    docs = load_corpus(csv_path, files_dir)

    assert [doc.csv_row_id for doc in docs] == ["000"]
    assert docs[0].doc_id == "doc:000"
    assert docs[0].text == ""
    assert docs[0].metadata["텍스트"] == "본문 텍스트"
    assert docs[0].metadata["budget_krw_int"] == 130000000
    assert docs[0].metadata["notice_round_int"] == 0
    assert docs[0].metadata["published_at_iso"] == "2024-10-04T13:51:23"
    assert docs[0].metadata["resolved_filesystem_path"].endswith(nfd_name)


def test_resolve_filename_map_indexes_both_nfc_and_nfd(tmp_path: Path) -> None:
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    nfc = "한국연구재단_기능개선.hwp"
    nfd = unicodedata.normalize("NFD", nfc)
    (files_dir / nfd).write_text("raw", encoding="utf-8")

    mapping = resolve_filename_map(files_dir)

    assert mapping[nfc].name == nfd
    assert mapping[nfd].name == nfd


def test_inspect_corpus_manifest_matches_reference_dataset(tmp_path: Path) -> None:
    out = tmp_path / "manifest.json"

    manifest = inspect_corpus(Path("data/data_list.csv"), Path("data/files"), out)

    saved = json.loads(out.read_text(encoding="utf-8"))
    assert manifest == saved
    assert manifest["row_count"] == 100
    assert manifest["text_nonempty_count"] == 100
    assert manifest["required_columns_present"] is True
    assert manifest["normalized_file_matches"] == 100
    assert manifest["suffix_counts"] == {".hwp": 96, ".pdf": 4}
    assert manifest["warnings"] == []
