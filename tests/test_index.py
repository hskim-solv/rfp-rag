from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from rfp_rag.build_index import build_index
from rfp_rag.chunking import chunk_document
from rfp_rag.corpus import CorpusDocument
from rfp_rag.providers import build_embeddings
from rfp_rag.vector_index import load_vector_store, search


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
        embedding_provider="fake",  # legacy alias, normalized to offline
    )

    saved = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert saved == manifest
    assert manifest["embedding_provider"] == "offline"
    assert manifest["vector_backend"] == "qdrant_local"
    assert manifest["unique_docs"] == 100
    assert manifest["chunk_count"] > 0
    assert (out / "chunks.jsonl").exists()
    assert (out / "qdrant").is_dir()

    store = load_vector_store(out / "qdrant", build_embeddings("offline"), lane="offline")
    results = search(store, "한영대학교 트랙운영 학사정보시스템 고도화", top_k=3)

    assert results
    # Hash embeddings lack the legacy exact-substring bonus, so assert top-3 (deterministic).
    reference = next((r for r in results if r.doc_id == "doc:000"), None)
    assert reference is not None
    assert reference.chunk_id.startswith("doc:000:chunk:")
    assert reference.score > 0


def test_build_index_creates_qdrant_collection_and_manifest(tmp_path: Path) -> None:
    out = tmp_path / "index"
    manifest = build_index(
        data_path=Path("data/data_list.csv"),
        files_path=Path("data/files"),
        out_dir=out,
        chunk_size=500,
        chunk_overlap=80,
        embedding_provider="fake",  # alias for offline
    )

    assert manifest["embedding_provider"] == "offline"
    assert manifest["embedding_model"] == "lexical-hash-v1"
    assert manifest["vector_backend"] == "qdrant_local"
    assert (out / "qdrant").is_dir()
    assert (out / "manifest.json").exists()
    assert (out / "chunks.jsonl").exists()


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
