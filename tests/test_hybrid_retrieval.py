from __future__ import annotations

from pathlib import Path

import pytest

from rfp_rag.chunking import Chunk
from rfp_rag.hybrid_retrieval import (
    BM25Index,
    fuse_ranked_results,
    load_chunk_results,
    tokenize,
)
from rfp_rag.index_store import save_index, SearchResult


def _chunk(chunk_id: str, text: str, project_name: str = "") -> Chunk:
    doc_num = chunk_id.split(":")[1]
    return Chunk(
        chunk_id=chunk_id,
        doc_id=f"doc:{doc_num}",
        csv_row_id=doc_num,
        text=text,
        metadata={
            "project_name": project_name,
            "issuer": "테스트기관",
            "csv_filename_raw": f"{doc_num}.pdf",
        },
    )


def _search_result(chunk_id: str, score: float) -> SearchResult:
    doc_num = chunk_id.split(":")[1]
    return SearchResult(
        chunk_id=chunk_id,
        doc_id=f"doc:{doc_num}",
        csv_row_id=doc_num,
        score=score,
        text=f"text {chunk_id}",
        metadata={"project_name": f"사업 {doc_num}", "issuer": "테스트기관"},
    )


def test_tokenize_keeps_korean_english_and_numbers() -> None:
    assert tokenize("AI 기반 LMS 2차 고도화, RFP-2026!") == [
        "ai",
        "기반",
        "lms",
        "2차",
        "고도화",
        "rfp",
        "2026",
    ]


def test_load_chunk_results_reads_chunks_jsonl(tmp_path: Path) -> None:
    out = tmp_path / "index"
    chunks = [_chunk("doc:000:chunk:0", "AI LMS 본문", "AI LMS 사업")]
    save_index(out, {"embedding_provider": "offline"}, chunks)

    loaded = load_chunk_results(out)

    assert loaded[0].chunk_id == "doc:000:chunk:0"
    assert loaded[0].doc_id == "doc:000"
    assert "사업명: AI LMS 사업" in loaded[0].text
    assert "발주기관: 테스트기관" in loaded[0].text
    assert loaded[0].metadata["csv_filename_raw"] == "000.pdf"


def test_bm25_scores_keyword_exact_chunk_first(tmp_path: Path) -> None:
    out = tmp_path / "index"
    chunks = [
        _chunk("doc:000:chunk:0", "AI 범용 시스템 유지보수", "일반 유지보수"),
        _chunk("doc:001:chunk:0", "AI LMS 학습 분석 추천 엔진 구축", "AI LMS 고도화"),
        _chunk("doc:002:chunk:0", "범용 시스템 유지보수", "일반 유지보수"),
    ]
    save_index(out, {"embedding_provider": "offline"}, chunks)
    index = BM25Index.from_index_dir(out)

    results = index.search("AI LMS 추천 엔진", top_k=3)

    assert [result.chunk_id for result in results] == ["doc:001:chunk:0", "doc:000:chunk:0"]
    assert results[0].score > results[1].score
    assert all(result.score > 0 for result in results)


def test_bm25_empty_query_returns_no_results(tmp_path: Path) -> None:
    out = tmp_path / "index"
    save_index(out, {"embedding_provider": "offline"}, [_chunk("doc:000:chunk:0", "AI LMS 본문")])
    index = BM25Index.from_index_dir(out)

    assert index.search("!!!", top_k=5) == []


def test_bm25_repeated_query_terms_do_not_change_ordering(tmp_path: Path) -> None:
    out = tmp_path / "index"
    chunks = [
        _chunk("doc:000:chunk:0", "AI 범용 시스템"),
        _chunk("doc:001:chunk:0", "LMS LMS 구축"),
    ]
    save_index(out, {"embedding_provider": "offline"}, chunks)
    index = BM25Index.from_index_dir(out)

    base = index.search("AI LMS", top_k=2)
    repeated = index.search("AI AI AI LMS", top_k=2)

    assert [result.chunk_id for result in base] == ["doc:001:chunk:0", "doc:000:chunk:0"]
    assert [result.chunk_id for result in repeated] == [result.chunk_id for result in base]


def test_fuse_ranked_results_normalizes_scores_to_rank_confidence() -> None:
    vector = [
        _search_result("doc:001:chunk:0", 0.90),
        _search_result("doc:000:chunk:0", 0.80),
    ]
    bm25 = [
        _search_result("doc:001:chunk:0", 12.0),
        _search_result("doc:002:chunk:0", 8.0),
    ]

    fused = fuse_ranked_results(vector, bm25, 3)
    vector_only = fuse_ranked_results([_search_result("doc:000:chunk:0", 0.90)], [], 1)

    assert fused[0].chunk_id == "doc:001:chunk:0"
    assert fused[0].score == 1.0
    assert vector_only[0].score == 0.7


def test_fuse_ranked_results_rejects_invalid_normalization_parameters() -> None:
    vector = [_search_result("doc:000:chunk:0", 0.90)]

    with pytest.raises(ValueError):
        fuse_ranked_results(vector, [], 1, rank_constant=-1)

    with pytest.raises(ValueError):
        fuse_ranked_results(vector, [], 1, vector_weight=0.0, bm25_weight=0.0)


def test_fuse_ranked_results_promotes_keyword_candidate() -> None:
    vector = [
        _search_result("doc:000:chunk:0", 0.90),
        _search_result("doc:001:chunk:0", 0.80),
    ]
    bm25 = [
        _search_result("doc:001:chunk:0", 12.0),
        _search_result("doc:002:chunk:0", 8.0),
    ]

    fused = fuse_ranked_results(vector, bm25, 3, vector_weight=0.7, bm25_weight=0.3, rank_constant=1)

    assert [r.chunk_id for r in fused] == [
        "doc:001:chunk:0",
        "doc:000:chunk:0",
        "doc:002:chunk:0",
    ]
    assert fused[0].score > fused[1].score


def test_fusion_tie_breaks_deterministically() -> None:
    vector = [_search_result("doc:002:chunk:0", 0.9), _search_result("doc:001:chunk:0", 0.8)]
    bm25 = [_search_result("doc:001:chunk:0", 12.0), _search_result("doc:002:chunk:0", 8.0)]

    fused = fuse_ranked_results(vector, bm25, 2, vector_weight=1.0, bm25_weight=1.0, rank_constant=60)

    assert fused[0].score == fused[1].score
    assert [r.chunk_id for r in fused] == ["doc:001:chunk:0", "doc:002:chunk:0"]
