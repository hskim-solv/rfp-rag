from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from rfp_rag.build_index import build_index
from rfp_rag.chunking import chunk_document
from rfp_rag.corpus import CorpusDocument
from rfp_rag.index_store import load_index, retrieve


def test_chunk_document_uses_doc_and_chunk_ids() -> None:
    doc = CorpusDocument(
        csv_row_id="007",
        doc_id="doc:007",
        text="첫 문단입니다. 둘째 문단입니다. " * 80,
        metadata={"project_name": "테스트", "issuer": "기관"},
    )

    chunks = chunk_document(doc, chunk_size=40, chunk_overlap=10)

    assert len(chunks) > 1
    assert chunks[0].chunk_id == "doc:007:chunk:0"
    assert chunks[0].doc_id == "doc:007"
    assert chunks[0].csv_row_id == "007"
    assert chunks[0].metadata["chunk_index"] == 0
    assert chunks[0].metadata["chunk_size"] == 40
    assert chunks[0].metadata["chunk_overlap"] == 10


def test_build_index_writes_manifest_and_retrieves_reference_doc(tmp_path: Path) -> None:
    out = tmp_path / "index"

    manifest = build_index(
        data_path=Path("data/data_list.csv"),
        files_path=Path("data/files"),
        out_dir=out,
        chunk_size=500,
        chunk_overlap=80,
        embedding_provider="fake",
    )

    saved = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert saved == manifest
    assert manifest["embedding_provider"] == "fake"
    assert manifest["vector_backend"] == "local_fake_lexical"
    assert manifest["unique_docs"] == 100
    assert manifest["chunk_count"] > 0
    assert (out / "chunks.jsonl").exists()

    index = load_index(out)
    results = retrieve(index, "한영대학교 트랙운영 학사정보시스템 고도화", top_k=3)

    assert results
    assert results[0].doc_id == "doc:000"
    assert results[0].chunk_id.startswith("doc:000:chunk:")
    assert results[0].score > 0


def test_build_index_rejects_malformed_corpus_before_indexing(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad.csv"
    files_dir = tmp_path / "files"
    files_dir.mkdir()
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
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({
            "공고 번호": "1",
            "공고 차수": "0",
            "사업명": "깨진 사업",
            "사업 금액": "",
            "발주 기관": "기관",
            "공개 일자": "",
            "입찰 참여 시작일": "",
            "입찰 참여 마감일": "",
            "사업 요약": "요약",
            "파일형식": "hwp",
            "파일명": "missing.hwp",
            "텍스트": "",
        })

    with pytest.raises(ValueError, match="corpus inspection failed"):
        build_index(
            data_path=csv_path,
            files_path=files_dir,
            out_dir=tmp_path / "index",
            chunk_size=500,
            chunk_overlap=80,
            embedding_provider="fake",
        )


def test_build_index_rejects_empty_required_metadata(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad_metadata.csv"
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    (files_dir / "ok.hwp").write_text("raw", encoding="utf-8")
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
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({
            "공고 번호": "1",
            "공고 차수": "0",
            "사업명": "",
            "사업 금액": "",
            "발주 기관": "기관",
            "공개 일자": "",
            "입찰 참여 시작일": "",
            "입찰 참여 마감일": "",
            "사업 요약": "요약",
            "파일형식": "hwp",
            "파일명": "ok.hwp",
            "텍스트": "본문",
        })

    with pytest.raises(ValueError, match="empty required values"):
        build_index(
            data_path=csv_path,
            files_path=files_dir,
            out_dir=tmp_path / "index",
            chunk_size=500,
            chunk_overlap=80,
            embedding_provider="fake",
        )
