from __future__ import annotations

from rfp_rag.chunking import Chunk
from rfp_rag.index_store import SearchResult
from rfp_rag.providers import LexicalHashEmbeddings, TemplateAnswerGenerator
from rfp_rag.rag_chain import answer_with_store
from rfp_rag.vector_index import build_vector_store


def _store():
    chunks = [
        Chunk(
            chunk_id="doc:000:chunk:0",
            doc_id="doc:000",
            csv_row_id="000",
            text="한영대학교 트랙운영 학사정보시스템 고도화 사업 제안요청서 본문",
            metadata={
                "project_name": "한영대학교 트랙운영 학사정보시스템 고도화",
                "issuer": "한영대학",
                "summary": "학사정보시스템 고도화 사업",
                "csv_filename_raw": "han.hwp",
            },
        )
    ]
    return build_vector_store(chunks, LexicalHashEmbeddings(dim=512), qdrant_path=None, lane="offline")


def test_in_domain_question_returns_cited_answer() -> None:
    response = answer_with_store(
        _store(),
        TemplateAnswerGenerator(),
        "한영대학교 트랙운영 학사정보시스템 고도화 사업을 요약해줘",
        top_k=3,
        min_score=0.05,
    )

    assert response["answer"]
    assert "없는 정보" not in response["answer"]
    assert response["sources"][0]["chunk_id"] == "doc:000:chunk:0"
    assert response["sources"][0]["chunk_id"] in response["retrieved_chunk_ids"]
    assert response["warnings"] == []
    assert response["confidence"] in {"medium", "high"}
    assert response["source_texts"]


def test_generator_abstention_sentinel_forces_abstain_despite_high_score() -> None:
    class _AbstainingGenerator:
        def generate(self, query: str, results: list[SearchResult]) -> str:
            return "검색된 근거만으로는 답할 수 없는 정보입니다."

    response = answer_with_store(
        _store(),
        _AbstainingGenerator(),
        "한영대학교 트랙운영 학사정보시스템 고도화 사업을 요약해줘",
        top_k=3,
        min_score=0.05,
    )

    # 검색 점수는 게이트를 통과했고, abstain은 생성기 측 sentinel이 유발한 것이어야 한다
    assert response["scores"] and response["scores"][0] >= 0.05
    assert "insufficient_context" in response["warnings"]
    assert response["confidence"] == "low"
    assert response["sources"] == []


def test_unrelated_question_abstains() -> None:
    response = answer_with_store(
        _store(),
        TemplateAnswerGenerator(),
        "화성 이주선 산소탱크 발사일은 언제야?",
        top_k=3,
        min_score=0.05,
    )

    assert "없는 정보" in response["answer"]
    assert "insufficient_context" in response["warnings"]
    assert response["confidence"] == "low"
    assert response["sources"] == []
    assert response["source_texts"] == []
