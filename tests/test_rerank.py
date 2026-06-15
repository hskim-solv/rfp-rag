from __future__ import annotations

import pytest

from rfp_rag.index_store import SearchResult
from rfp_rag.rerank import (
    LLMRerankOutput,
    LLMRerankRank,
    LLMReranker,
    RERANKER_LLM,
    RERANKER_NONE,
    build_reranker,
)


def _result(chunk_id: str, text: str, score: float) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        doc_id=chunk_id.split(":chunk:")[0],
        csv_row_id=chunk_id.split(":")[1],
        score=score,
        text=text,
        metadata={"project_name": "테스트 사업", "issuer": "테스트기관"},
    )


def test_llm_reranker_reorders_candidates_and_records_scores() -> None:
    candidates = [
        _result("doc:000:chunk:0", "일반 유지보수", 0.91),
        _result("doc:001:chunk:0", "AI LMS 추천 엔진 학습 분석", 0.88),
    ]

    def invoke(prompt: str) -> LLMRerankOutput:
        assert "doc:000:chunk:0" in prompt
        assert "doc:001:chunk:0" in prompt
        return LLMRerankOutput(
            ranks=[
                LLMRerankRank(chunk_id="doc:001:chunk:0", relevance_score=0.97),
                LLMRerankRank(chunk_id="doc:000:chunk:0", relevance_score=0.31),
            ]
        )

    reranker = LLMReranker(invoke=invoke)
    results = reranker.rerank("AI LMS 추천 엔진", candidates, top_k=1)

    assert [result.chunk_id for result in results] == ["doc:001:chunk:0"]
    assert results[0].metadata["reranker"] == "llm"
    assert results[0].metadata["reranker_score"] == 0.97
    assert results[0].metadata["pre_rerank_score"] == 0.88


def test_llm_reranker_falls_back_to_original_order_for_invalid_chunk_ids() -> None:
    candidates = [
        _result("doc:000:chunk:0", "일반 유지보수", 0.91),
        _result("doc:001:chunk:0", "AI LMS 추천 엔진 학습 분석", 0.88),
    ]
    reranker = LLMReranker(
        invoke=lambda _prompt: LLMRerankOutput(
            ranks=[LLMRerankRank(chunk_id="missing", relevance_score=1.0)]
        )
    )

    results = reranker.rerank("AI LMS 추천 엔진", candidates, top_k=2)

    assert [result.chunk_id for result in results] == [
        "doc:000:chunk:0",
        "doc:001:chunk:0",
    ]


def test_build_reranker_keeps_none_as_default_and_blocks_offline_llm() -> None:
    assert build_reranker("offline", RERANKER_NONE) is None

    with pytest.raises(ValueError, match="LLM reranker requires real_openai or open"):
        build_reranker("offline", RERANKER_LLM)
