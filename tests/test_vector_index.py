from __future__ import annotations

from pathlib import Path

import pytest

from rfp_rag.chunking import Chunk
from rfp_rag.index_store import SearchResult, save_index
from rfp_rag.providers import LexicalHashEmbeddings
from rfp_rag.vector_index import (
    RETRIEVAL_BM25,
    RETRIEVAL_HYBRID,
    RETRIEVAL_VECTOR,
    add_documents_in_batches,
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
            metadata={
                "project_name": "한영대학교 트랙운영 학사정보시스템 고도화",
                "issuer": "한영대학",
            },
        ),
        Chunk(
            chunk_id="doc:001:chunk:0",
            doc_id="doc:001",
            csv_row_id="001",
            text="국립중앙도서관 자료보존 환경 개선 사업 본문",
            metadata={
                "project_name": "국립중앙도서관 자료보존 환경 개선",
                "issuer": "국립중앙도서관",
            },
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


def test_add_documents_in_batches_uses_configured_small_batch_size() -> None:
    calls = []

    class Store:
        def add_documents(self, *, documents, ids, batch_size):
            calls.append(
                {
                    "documents": documents,
                    "ids": ids,
                    "batch_size": batch_size,
                }
            )

    add_documents_in_batches(
        Store(), documents=["a", "b"], ids=["1", "2"], batch_size=7
    )

    assert calls == [
        {
            "documents": ["a", "b"],
            "ids": ["1", "2"],
            "batch_size": 7,
        }
    ]


def test_persist_and_reload_roundtrip(tmp_path: Path) -> None:
    emb = LexicalHashEmbeddings(dim=512)
    qdrant_path = tmp_path / "qdrant"
    store = build_vector_store(_chunks(), emb, qdrant_path=qdrant_path, lane="offline")
    del (
        store
    )  # drops the only ref; CPython refcounting closes the Qdrant lock immediately

    reloaded = load_vector_store(qdrant_path, emb, lane="offline")
    results = search(reloaded, "국립중앙도서관 자료보존", top_k=1)

    assert results[0].chunk_id == "doc:001:chunk:0"


def test_search_returns_at_most_top_k() -> None:
    emb = LexicalHashEmbeddings(dim=512)
    store = build_vector_store(_chunks(), emb, qdrant_path=None, lane="offline")

    assert len(search(store, "사업", top_k=1)) == 1
    assert len(search(store, "사업", top_k=1, retrieval_mode=RETRIEVAL_VECTOR)) == 1


def test_vector_search_with_index_dir_injects_exact_section_title_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chunks = [
        Chunk(
            chunk_id="doc:000:chunk:0",
            doc_id="doc:000",
            csv_row_id="000",
            text="일반 본문",
            metadata={
                "project_name": "테스트 사업",
                "issuer": "테스트기관",
                "section_title": "일반",
                "section_type": "general",
            },
        ),
        Chunk(
            chunk_id="doc:000:chunk:1",
            doc_id="doc:000",
            csv_row_id="000",
            text="입찰 참가자격과 입찰방식 본문",
            metadata={
                "project_name": "테스트 사업",
                "issuer": "테스트기관",
                "section_title": "입찰방식",
                "section_type": "submission",
                "section_path": ["입찰 및 계약", "입찰방식"],
            },
        ),
    ]
    index_dir = tmp_path / "index"
    save_index(index_dir, {"embedding_provider": "offline"}, chunks)

    def fake_vector_search(store: object, query: str, top_k: int = 5):
        return [
            SearchResult(
                chunk_id="doc:000:chunk:0",
                doc_id="doc:000",
                csv_row_id="000",
                score=0.7,
                text="일반 본문",
                metadata=chunks[0].metadata,
            )
        ]

    monkeypatch.setattr("rfp_rag.vector_index._vector_search", fake_vector_search)

    results = search(
        object(),
        "테스트 사업의 입찰방식 섹션 내용을 알려줘",
        top_k=1,
        retrieval_mode=RETRIEVAL_VECTOR,
        index_dir=index_dir,
    )

    assert results[0].chunk_id == "doc:000:chunk:1"
    assert results[0].metadata["section_title"] == "입찰방식"


def test_vector_search_with_index_dir_injects_exact_project_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index_dir = tmp_path / "index"
    chunks = [
        Chunk(
            chunk_id="doc:021:chunk:0",
            doc_id="doc:021",
            csv_row_id="021",
            text="원 공고 본문",
            metadata={
                "project_name": "의료기기산업 종합정보시스템 기능개선 사업",
                "issuer": "한국보건산업진흥원",
            },
        ),
        Chunk(
            chunk_id="doc:046:chunk:0",
            doc_id="doc:046",
            csv_row_id="046",
            text="2차 공고 본문",
            metadata={
                "project_name": "의료기기산업 종합정보시스템 기능개선 사업(2차)",
                "issuer": "BioIN",
            },
        ),
    ]
    save_index(index_dir, {"embedding_provider": "offline"}, chunks)

    def fake_vector_search(store: object, query: str, top_k: int = 5):
        return [
            SearchResult(
                chunk_id="doc:046:chunk:0",
                doc_id="doc:046",
                csv_row_id="046",
                score=0.8,
                text="2차 공고 본문",
                metadata=chunks[1].metadata,
            )
        ]

    monkeypatch.setattr("rfp_rag.vector_index._vector_search", fake_vector_search)

    results = search(
        object(),
        "의료기기산업 종합정보시스템 기능개선 사업 사업 금액은 얼마야?",
        top_k=1,
        retrieval_mode=RETRIEVAL_VECTOR,
        index_dir=index_dir,
    )

    assert results[0].doc_id == "doc:021"


def test_vector_search_with_index_dir_keeps_multiple_project_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index_dir = tmp_path / "index"
    chunks = [
        Chunk(
            chunk_id="doc:000:chunk:0",
            doc_id="doc:000",
            csv_row_id="000",
            text="A 본문",
            metadata={"project_name": "A 사업", "issuer": "A 기관"},
        ),
        Chunk(
            chunk_id="doc:050:chunk:0",
            doc_id="doc:050",
            csv_row_id="050",
            text="B 본문",
            metadata={"project_name": "B 사업", "issuer": "B 기관"},
        ),
    ]
    save_index(index_dir, {"embedding_provider": "offline"}, chunks)

    def fake_vector_search(store: object, query: str, top_k: int = 5):
        return [
            SearchResult(
                chunk_id="doc:000:chunk:0",
                doc_id="doc:000",
                csv_row_id="000",
                score=0.8,
                text="A 본문",
                metadata=chunks[0].metadata,
            )
        ]

    monkeypatch.setattr("rfp_rag.vector_index._vector_search", fake_vector_search)

    results = search(
        object(),
        "A 사업과 B 사업의 사업 금액을 비교해줘",
        top_k=2,
        retrieval_mode=RETRIEVAL_VECTOR,
        index_dir=index_dir,
    )

    assert {result.doc_id for result in results} == {"doc:000", "doc:050"}


def test_vector_section_candidate_cache_refreshes_when_chunks_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index_dir = tmp_path / "index"

    def fake_vector_search(store: object, query: str, top_k: int = 5):
        return [
            SearchResult(
                chunk_id="doc:999:chunk:0",
                doc_id="doc:999",
                csv_row_id="999",
                score=0.1,
                text="fallback",
                metadata={"project_name": "fallback", "issuer": "기관"},
            )
        ]

    monkeypatch.setattr("rfp_rag.vector_index._vector_search", fake_vector_search)

    save_index(
        index_dir,
        {"embedding_provider": "offline"},
        [
            Chunk(
                chunk_id="doc:000:chunk:0",
                doc_id="doc:000",
                csv_row_id="000",
                text="입찰방식 본문",
                metadata={
                    "project_name": "테스트 사업",
                    "issuer": "기관",
                    "section_title": "입찰방식",
                },
            )
        ],
    )
    first = search(
        object(),
        "테스트 사업의 입찰방식 섹션 내용을 알려줘",
        top_k=1,
        index_dir=index_dir,
    )

    save_index(
        index_dir,
        {"embedding_provider": "offline"},
        [
            Chunk(
                chunk_id="doc:001:chunk:0",
                doc_id="doc:001",
                csv_row_id="001",
                text="평가방법 본문이 더 길어져서 chunks.jsonl size도 달라진다",
                metadata={
                    "project_name": "테스트 사업",
                    "issuer": "기관",
                    "section_title": "평가방법",
                },
            )
        ],
    )
    second = search(
        object(),
        "테스트 사업의 평가방법 섹션 내용을 알려줘",
        top_k=1,
        index_dir=index_dir,
    )

    assert first[0].chunk_id == "doc:000:chunk:0"
    assert second[0].chunk_id == "doc:001:chunk:0"


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


def test_bm25_search_requires_index_dir() -> None:
    emb = LexicalHashEmbeddings(dim=512)
    store = build_vector_store(_chunks(), emb, qdrant_path=None, lane="offline")

    with pytest.raises(ValueError, match="index_dir is required"):
        search(store, "사업", top_k=1, retrieval_mode=RETRIEVAL_BM25)


def test_bm25_search_uses_keyword_index(tmp_path: Path) -> None:
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
        retrieval_mode=RETRIEVAL_BM25,
        index_dir=index_dir,
    )

    assert results[0].chunk_id == "doc:001:chunk:0"
    assert results[0].score > 0


def test_hybrid_search_top_k_zero_returns_empty_without_index_dir() -> None:
    emb = LexicalHashEmbeddings(dim=512)
    store = build_vector_store(_chunks(), emb, qdrant_path=None, lane="offline")

    assert search(store, "사업", top_k=0, retrieval_mode=RETRIEVAL_HYBRID) == []


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


def test_hybrid_search_without_bm25_match_preserves_vector_scores(
    tmp_path: Path,
) -> None:
    chunks = _chunks()
    emb = LexicalHashEmbeddings(dim=512)
    index_dir = tmp_path / "index"
    save_index(index_dir, {"embedding_provider": "offline"}, chunks)
    store = build_vector_store(chunks, emb, qdrant_path=None, lane="offline")

    vector_results = search(
        store, "우주정거장", top_k=2, retrieval_mode=RETRIEVAL_VECTOR
    )
    hybrid_results = search(
        store,
        "우주정거장",
        top_k=2,
        retrieval_mode=RETRIEVAL_HYBRID,
        index_dir=index_dir,
    )

    assert [(r.chunk_id, r.score) for r in hybrid_results] == [
        (r.chunk_id, r.score) for r in vector_results
    ]


def test_hybrid_search_reuses_bm25_index_for_same_index_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chunks = _chunks()
    emb = LexicalHashEmbeddings(dim=512)
    index_dir = tmp_path / "index"
    save_index(index_dir, {"embedding_provider": "offline"}, chunks)
    store = build_vector_store(chunks, emb, qdrant_path=None, lane="offline")

    from rfp_rag.hybrid_retrieval import BM25Index

    calls = 0
    original = BM25Index.from_index_dir.__func__

    def counting_from_index_dir(cls, path: Path | str) -> BM25Index:
        nonlocal calls
        calls += 1
        return original(cls, path)

    monkeypatch.setattr(
        BM25Index,
        "from_index_dir",
        classmethod(counting_from_index_dir),
    )

    search(
        store,
        "학사정보시스템",
        top_k=1,
        retrieval_mode=RETRIEVAL_HYBRID,
        index_dir=index_dir,
    )
    search(
        store,
        "사업",
        top_k=1,
        retrieval_mode=RETRIEVAL_HYBRID,
        index_dir=index_dir,
    )

    assert calls == 1
