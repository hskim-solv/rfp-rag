from __future__ import annotations

import os

import pytest

from rfp_rag.providers import build_embeddings

pytestmark = pytest.mark.real

requires_key = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"
)


@requires_key
def test_openai_embeddings_smoke() -> None:
    emb = build_embeddings("real_openai")

    vector = emb.embed_query("한영대학교 학사정보시스템 고도화 사업")

    assert len(vector) >= 256
    assert any(v != 0.0 for v in vector)


@requires_key
def test_llm_generator_smoke() -> None:
    from rfp_rag.index_store import SearchResult
    from rfp_rag.providers import LLMAnswerGenerator

    result = SearchResult(
        chunk_id="doc:000:chunk:0",
        doc_id="doc:000",
        csv_row_id="000",
        score=0.9,
        text="사업명: 한영대학교 학사정보시스템 고도화\n발주기관: 한영대학\n예산은 1억 5천만원이다.",
        metadata={"project_name": "한영대학교 학사정보시스템 고도화", "issuer": "한영대학"},
    )
    gen = LLMAnswerGenerator()

    answer = gen.generate("이 사업 발주 기관은 어디야?", [result])

    assert "한영대학" in answer
