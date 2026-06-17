from __future__ import annotations

import json
from pathlib import Path

import pytest

from rfp_rag.chunking import Chunk
from rfp_rag.index_store import SearchResult
from rfp_rag.providers import LexicalHashEmbeddings, TemplateAnswerGenerator
from rfp_rag.rag_chain import answer_query, answer_with_store
from rfp_rag.vector_index import build_vector_store
from rfp_rag.visual_sidecar import VisualEvidenceIndex


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
    return build_vector_store(
        chunks, LexicalHashEmbeddings(dim=512), qdrant_path=None, lane="offline"
    )


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
    # 생성기 프롬프트와 RAGAS judge가 같은 컨텍스트를 봐야 한다: 메타데이터 라인 + 본문
    assert "발주기관: 한영대학" in response["source_texts"][0]
    assert (
        "한영대학교 트랙운영 학사정보시스템 고도화 사업 제안요청서 본문"
        in response["source_texts"][0]
    )


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


def test_generator_abstention_can_preserve_retrieved_sources_for_eval() -> None:
    class _AbstainingGenerator:
        def generate(self, query: str, results: list[SearchResult]) -> str:
            return "검색된 근거만으로는 답할 수 없는 정보입니다."

    response = answer_with_store(
        _store(),
        _AbstainingGenerator(),
        "한영대학교 트랙운영 학사정보시스템 고도화 사업을 요약해줘",
        top_k=3,
        min_score=0.05,
        preserve_generator_abstention_sources=True,
    )

    assert "insufficient_context" in response["warnings"]
    assert response["confidence"] == "low"
    assert response["sources"][0]["chunk_id"] == "doc:000:chunk:0"
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


def test_answer_query_rejects_lane_mismatch(tmp_path: Path) -> None:
    d = tmp_path / "idx"
    d.mkdir()
    (d / "manifest.json").write_text(
        json.dumps({"embedding_provider": "real_openai"}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="rebuild the index"):
        answer_query(d, "질문", provider="offline")


def test_answer_query_requires_manifest(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="manifest not found"):
        answer_query(tmp_path / "empty", "질문")


def test_answer_with_store_rejects_hybrid_without_index_dir() -> None:
    with pytest.raises(ValueError, match="index_dir is required"):
        answer_with_store(
            _store(),
            TemplateAnswerGenerator(),
            "한영대학교 학사정보시스템",
            retrieval_mode="hybrid",
        )


def test_answer_with_store_attaches_visual_sidecar_context() -> None:
    visual_index = VisualEvidenceIndex(
        by_doc_id={
            "doc:000": [
                {
                    "record_id": "doc:000:p3:gantt_schedule",
                    "doc_id": "doc:000",
                    "page": 3,
                    "visual_type": "gantt_schedule",
                    "value": "Gantt-style project schedule is present on the selected page",
                    "extractor": "visual_tesseract_ocr_candidate_v2",
                    "confidence": 0.81,
                }
            ]
        }
    )

    response = answer_with_store(
        _store(),
        TemplateAnswerGenerator(),
        "한영대학교 트랙운영 학사정보시스템 고도화 사업을 요약해줘",
        top_k=3,
        min_score=0.05,
        visual_evidence_index=visual_index,
    )

    assert response["sources"][0]["visual_evidence"][0]["record_id"] == (
        "doc:000:p3:gantt_schedule"
    )
    assert "시각근거:" in response["source_texts"][0]


def test_answer_with_store_can_rerank_more_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_results = [
        SearchResult(
            chunk_id="doc:000:chunk:0",
            doc_id="doc:000",
            csv_row_id="000",
            score=0.91,
            text="일반 유지보수",
            metadata={"project_name": "일반 유지보수", "issuer": "기관"},
        ),
        SearchResult(
            chunk_id="doc:001:chunk:0",
            doc_id="doc:001",
            csv_row_id="001",
            score=0.89,
            text="AI LMS 추천 엔진",
            metadata={"project_name": "AI LMS 고도화", "issuer": "기관"},
        ),
    ]

    def fake_search(*args, **kwargs):
        assert kwargs["top_k"] == 10
        return raw_results

    class _Reranker:
        name = "test"

        def rerank(
            self, query: str, results: list[SearchResult], top_k: int
        ) -> list[SearchResult]:
            assert query == "AI LMS 추천 엔진"
            assert top_k == 1
            return [results[1]]

    class _Generator:
        def generate(self, query: str, results: list[SearchResult]) -> str:
            assert [result.chunk_id for result in results] == ["doc:001:chunk:0"]
            return "AI LMS 고도화 근거 답변"

    monkeypatch.setattr("rfp_rag.rag_chain.search", fake_search)

    response = answer_with_store(
        object(),
        _Generator(),
        "AI LMS 추천 엔진",
        top_k=1,
        min_score=0.1,
        reranker=_Reranker(),
        rerank_candidate_k=10,
    )

    assert response["retrieved_chunk_ids"] == ["doc:001:chunk:0"]
    assert response["reranker"] == "test"
    assert response["rerank_candidate_k"] == 10


def test_answer_with_store_preserves_reranker_metadata_on_abstention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_results = [
        SearchResult(
            chunk_id="doc:000:chunk:0",
            doc_id="doc:000",
            csv_row_id="000",
            score=0.91,
            text="일반 유지보수",
            metadata={"project_name": "일반 유지보수", "issuer": "기관"},
        )
    ]

    class _Reranker:
        name = "test"

        def rerank(
            self, query: str, results: list[SearchResult], top_k: int
        ) -> list[SearchResult]:
            metadata = dict(results[0].metadata)
            metadata["reranker_score"] = 0.42
            return [
                SearchResult(
                    chunk_id=results[0].chunk_id,
                    doc_id=results[0].doc_id,
                    csv_row_id=results[0].csv_row_id,
                    score=results[0].score,
                    text=results[0].text,
                    metadata=metadata,
                )
            ]

    class _AbstainingGenerator:
        def generate(self, query: str, results: list[SearchResult]) -> str:
            return "없는 정보"

    monkeypatch.setattr(
        "rfp_rag.rag_chain.search",
        lambda *args, **kwargs: raw_results,
    )

    response = answer_with_store(
        object(),
        _AbstainingGenerator(),
        "AI LMS 추천 엔진",
        top_k=1,
        min_score=0.1,
        reranker=_Reranker(),
        rerank_candidate_k=10,
    )

    assert response["warnings"] == ["insufficient_context"]
    assert response["reranker"] == "test"
    assert response["rerank_candidate_k"] == 10
    assert response["reranker_scores"] == [0.42]
