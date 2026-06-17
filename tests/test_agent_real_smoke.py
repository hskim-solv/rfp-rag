from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.real

requires_key = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"
)


@requires_key
def test_llm_router_classifies_metadata_query() -> None:
    from rfp_rag.agent.brains import LLMRouter

    d = LLMRouter().route("사업 금액이 가장 큰 공고 3건은 뭐야?")
    assert d.route == "metadata_query"
    assert d.tool_args.get("sort_by") == "budget_krw_int"


@requires_key
def test_llm_router_classifies_rag_query_with_save_flag() -> None:
    from rfp_rag.agent.brains import LLMRouter

    d = LLMRouter().route(
        "한영대학교 학사정보시스템 고도화 사업을 요약해서 보고서로 저장해줘"
    )
    assert d.route == "rag_query"
    assert d.save_requested is True


@requires_key
def test_llm_rewriter_strips_noise() -> None:
    from rfp_rag.agent.brains import LLMQueryRewriter

    q = "안녕하세요 혹시 다른 건 말고 한영대학교 트랙운영 학사정보시스템 고도화 사업 예산이 궁금해요"
    rewritten = LLMQueryRewriter().rewrite(q, attempt=1)
    assert "한영대학교" in rewritten
    assert len(rewritten) < len(q)
