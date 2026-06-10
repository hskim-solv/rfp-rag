from __future__ import annotations

from rfp_rag.chunking import Chunk
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
