from __future__ import annotations

from pathlib import Path

from rfp_rag.ask import answer_query
from rfp_rag.build_index import build_index


def _index(tmp_path: Path) -> Path:
    out = tmp_path / "index"
    build_index(
        data_path=Path("data/data_list.csv"),
        files_path=Path("data/files"),
        out_dir=out,
        chunk_size=500,
        chunk_overlap=80,
        embedding_provider="fake",
    )
    return out


def test_answer_query_uses_retrieved_context_and_cites_doc_chunk(tmp_path: Path) -> None:
    index_dir = _index(tmp_path)

    response = answer_query(index_dir, "한영대학교 트랙운영 학사정보시스템 고도화 사업을 요약해줘", top_k=3)

    assert response["answer"]
    assert "없는 정보" not in response["answer"]
    assert response["sources"]
    assert response["sources"][0]["doc_id"] == "doc:000"
    assert response["sources"][0]["chunk_id"].startswith("doc:000:chunk:")
    assert response["sources"][0]["chunk_id"] in response["retrieved_chunk_ids"]
    assert response["warnings"] == []


def test_answer_query_abstains_when_context_is_insufficient(tmp_path: Path) -> None:
    index_dir = _index(tmp_path)

    response = answer_query(index_dir, "화성 이주선 산소탱크 발사일은 언제야?", top_k=3)

    assert "없는 정보" in response["answer"]
    assert "insufficient_context" in response["warnings"]
    assert response["confidence"] == "low"
    assert response["sources"] == []
