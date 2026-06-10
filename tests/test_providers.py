from __future__ import annotations

import math

import pytest

from rfp_rag.index_store import SearchResult
from rfp_rag.providers import (
    LANE_OFFLINE,
    LANE_REAL_OPENAI,
    LexicalHashEmbeddings,
    LLMAnswer,
    LLMAnswerGenerator,
    TemplateAnswerGenerator,
    build_answer_prompt,
    build_embeddings,
    normalize_lane,
)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def test_lexical_hash_embeddings_are_deterministic_and_unit_norm() -> None:
    emb = LexicalHashEmbeddings(dim=512)

    v1 = emb.embed_query("한영대학교 트랙운영 학사정보시스템 고도화")
    v2 = emb.embed_query("한영대학교 트랙운영 학사정보시스템 고도화")

    assert len(v1) == 512
    assert v1 == v2
    assert abs(math.sqrt(sum(x * x for x in v1)) - 1.0) < 1e-6


def test_related_text_scores_higher_than_unrelated() -> None:
    emb = LexicalHashEmbeddings(dim=512)

    doc = emb.embed_query("한영대학교 트랙운영 학사정보시스템 고도화 사업 제안요청서")
    related = emb.embed_query("한영대학교 학사정보시스템 사업 요약해줘")
    unrelated = emb.embed_query("화성 이주선 산소탱크 발사일은 언제야?")

    assert _cosine(doc, related) > _cosine(doc, unrelated)
    assert _cosine(doc, unrelated) < 0.25


def test_embed_documents_matches_embed_query() -> None:
    emb = LexicalHashEmbeddings(dim=256)

    docs = emb.embed_documents(["입찰 공고", "사업 요약"])

    assert len(docs) == 2
    assert docs[0] == emb.embed_query("입찰 공고")


def _result(score: float = 0.8) -> SearchResult:
    return SearchResult(
        chunk_id="doc:000:chunk:0",
        doc_id="doc:000",
        csv_row_id="000",
        score=score,
        text="트랙운영 학사정보시스템 고도화 본문",
        metadata={
            "project_name": "한영대학교 트랙운영 학사정보시스템 고도화",
            "issuer": "한영대학",
            "summary": "학사정보시스템을 고도화한다.",
            "budget_krw_int": 150000000,
            "bid_end_at_iso": "2024-05-01T10:00:00",
        },
    )


def test_template_generator_answers_budget_from_metadata() -> None:
    gen = TemplateAnswerGenerator()

    answer = gen.generate("한영대학교 사업 금액은 얼마야?", [_result()])

    assert "150,000,000" in answer
    assert "없는 정보" not in answer


def test_template_generator_falls_back_to_context_answer() -> None:
    gen = TemplateAnswerGenerator()

    answer = gen.generate("이 사업의 추진 배경 알려줘", [_result()])

    assert "한영대학교 트랙운영 학사정보시스템 고도화" in answer
    assert "한영대학" in answer


def test_build_answer_prompt_labels_chunks_and_includes_query() -> None:
    prompt = build_answer_prompt("발주 기관은 어디야?", [_result()])

    assert "[doc:000:chunk:0]" in prompt
    assert "발주 기관은 어디야?" in prompt
    assert "트랙운영 학사정보시스템 고도화 본문" in prompt


def test_llm_generator_keeps_only_valid_citations() -> None:
    def fake_invoke(prompt: str) -> LLMAnswer:
        return LLMAnswer(
            answer="발주 기관은 한영대학입니다.",
            cited_chunk_ids=["doc:000:chunk:0", "doc:999:chunk:9"],
            insufficient_context=False,
        )

    gen = LLMAnswerGenerator(invoke=fake_invoke)

    answer = gen.generate("발주 기관은 어디야?", [_result()])

    assert answer == "발주 기관은 한영대학입니다."
    assert gen.last_cited_chunk_ids == ["doc:000:chunk:0"]


def test_llm_generator_signals_abstention_via_phrase() -> None:
    def fake_invoke(prompt: str) -> LLMAnswer:
        return LLMAnswer(answer="자료가 없습니다.", cited_chunk_ids=[], insufficient_context=True)

    gen = LLMAnswerGenerator(invoke=fake_invoke)

    answer = gen.generate("화성 기지 예산은?", [_result()])

    assert "없는 정보" in answer


def test_normalize_lane_accepts_aliases() -> None:
    assert normalize_lane("offline") == LANE_OFFLINE
    assert normalize_lane("fake") == LANE_OFFLINE
    assert normalize_lane("fake_offline") == LANE_OFFLINE
    assert normalize_lane("openai") == LANE_REAL_OPENAI
    assert normalize_lane("real_openai") == LANE_REAL_OPENAI


def test_normalize_lane_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unknown lane"):
        normalize_lane("cohere")


def test_build_embeddings_offline_is_lexical_hash() -> None:
    assert isinstance(build_embeddings(LANE_OFFLINE), LexicalHashEmbeddings)


def test_build_embeddings_real_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY required"):
        build_embeddings(LANE_REAL_OPENAI)
