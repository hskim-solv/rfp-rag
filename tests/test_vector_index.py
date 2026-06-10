from __future__ import annotations

from pathlib import Path

from rfp_rag.chunking import Chunk
from rfp_rag.providers import LexicalHashEmbeddings
from rfp_rag.vector_index import build_vector_store, load_vector_store, search


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


def test_build_and_search_preserves_chunk_identity(tmp_path: Path) -> None:
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
    del store

    reloaded = load_vector_store(qdrant_path, emb, lane="offline")
    results = search(reloaded, "국립중앙도서관 자료보존", top_k=1)

    assert results[0].chunk_id == "doc:001:chunk:0"


def test_search_returns_at_most_top_k(tmp_path: Path) -> None:
    emb = LexicalHashEmbeddings(dim=512)
    store = build_vector_store(_chunks(), emb, qdrant_path=None, lane="offline")

    assert len(search(store, "사업", top_k=1)) == 1
