from __future__ import annotations

from pathlib import Path

import pytest

from rfp_rag.chunking import Chunk
from rfp_rag.index_store import save_index
from rfp_rag.providers import LexicalHashEmbeddings
from rfp_rag.vector_index import (
    RETRIEVAL_HYBRID,
    RETRIEVAL_VECTOR,
    build_vector_store,
    load_vector_store,
    search,
)


def _chunks() -> list[Chunk]:
    return [
        Chunk(
            chunk_id="doc:000:chunk:0",
            doc_id="doc:000",
            csv_row_id="000",
            text="한영대학교 트랙운영 학사정보시스템 고도화 사업 본문",
            metadata={"project_name": "한영대학교 트랙운영 학사정보시스템 고도화", "issuer": "한영대학"},
        ),
        Chunk(
            chunk_id="doc:001:chunk:0",
            doc_id="doc:001",
            csv_row_id="001",
            text="국립중앙도서관 자료보존 환경 개선 사업 본문",
            metadata={"project_name": "국립중앙도서관 자료보존 환경 개선", "issuer": "국립중앙도서관"},
        ),
    ]


def test_build_and_search_preserves_chunk_identity() -> None:
    emb = LexicalHashEmbeddings(dim=512)
    store = build_vector_store(_chunks(), emb, qdrant_path=None, lane="offline")

    results = search(store, "한영대학교 학사정보시스템 사업", top_k=2)

    assert results[0].chunk_id == "doc:000:chunk:0"
    assert results[0].doc_id == "doc:000"
    assert results[0].csv_row_id == "000"
    assert results[0].metadata["issuer"] == "한영대학"
    assert results[0].score >= results[1].score
    assert "학사정보시스템" in results[0].text


def test_persist_and_reload_roundtrip(tmp_path: Path) -> None:
    emb = LexicalHashEmbeddings(dim=512)
    qdrant_path = tmp_path / "qdrant"
    store = build_vector_store(_chunks(), emb, qdrant_path=qdrant_path, lane="offline")
    del store  # drops the only ref; CPython refcounting closes the Qdrant lock immediately

    reloaded = load_vector_store(qdrant_path, emb, lane="offline")
    results = search(reloaded, "국립중앙도서관 자료보존", top_k=1)

    assert results[0].chunk_id == "doc:001:chunk:0"


def test_search_returns_at_most_top_k() -> None:
    emb = LexicalHashEmbeddings(dim=512)
    store = build_vector_store(_chunks(), emb, qdrant_path=None, lane="offline")

    assert len(search(store, "사업", top_k=1)) == 1
    assert len(search(store, "사업", top_k=1, retrieval_mode=RETRIEVAL_VECTOR)) == 1


def test_search_rejects_unknown_retrieval_mode() -> None:
    emb = LexicalHashEmbeddings(dim=512)
    store = build_vector_store(_chunks(), emb, qdrant_path=None, lane="offline")

    with pytest.raises(ValueError, match="unknown retrieval_mode"):
        search(store, "사업", top_k=1, retrieval_mode="magic")


def test_hybrid_search_requires_index_dir() -> None:
    emb = LexicalHashEmbeddings(dim=512)
    store = build_vector_store(_chunks(), emb, qdrant_path=None, lane="offline")

    with pytest.raises(ValueError, match="index_dir is required"):
        search(store, "사업", top_k=1, retrieval_mode=RETRIEVAL_HYBRID)


def test_hybrid_search_promotes_keyword_candidate(tmp_path: Path) -> None:
    chunks = [
        Chunk(
            chunk_id="doc:000:chunk:0",
            doc_id="doc:000",
            csv_row_id="000",
            text="범용 시스템 유지보수",
            metadata={"project_name": "일반 유지보수", "issuer": "테스트기관"},
        ),
        Chunk(
            chunk_id="doc:001:chunk:0",
            doc_id="doc:001",
            csv_row_id="001",
            text="AI LMS 추천 엔진 학습 분석",
            metadata={"project_name": "AI LMS 고도화", "issuer": "테스트기관"},
        ),
    ]
    emb = LexicalHashEmbeddings(dim=512)
    index_dir = tmp_path / "index"
    save_index(index_dir, {"embedding_provider": "offline"}, chunks)
    store = build_vector_store(chunks, emb, qdrant_path=None, lane="offline")

    results = search(
        store,
        "AI LMS 추천 엔진",
        top_k=1,
        retrieval_mode=RETRIEVAL_HYBRID,
        index_dir=index_dir,
    )

    assert results[0].chunk_id == "doc:001:chunk:0"
    assert results[0].score > 0
