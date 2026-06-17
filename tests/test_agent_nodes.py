from __future__ import annotations

from pathlib import Path

from rfp_rag.agent.brains import RuleQueryRewriter, RuleRouter
from rfp_rag.agent.nodes import AgentRuntime
from rfp_rag.agent.tools import AuditLogger
from rfp_rag.chunking import Chunk
from rfp_rag.corpus import CorpusDocument
from rfp_rag.providers import LexicalHashEmbeddings, TemplateAnswerGenerator
from rfp_rag.vector_index import build_vector_store

PROJECT = "한영대학교 트랙운영 학사정보시스템 고도화"


def _runtime(tmp_path: Path, min_score: float = 0.05) -> AgentRuntime:
    chunks = [
        Chunk(
            chunk_id="doc:000:chunk:0",
            doc_id="doc:000",
            csv_row_id="000",
            text=f"{PROJECT} 사업 제안요청서 본문",
            metadata={
                "project_name": PROJECT,
                "issuer": "한영대학",
                "summary": "학사정보시스템 고도화 사업",
                "budget_krw_int": 130_000_000,
                "bid_end_at_iso": "2024-10-15T17:00:00",
                "csv_filename_raw": "han.hwp",
            },
        )
    ]
    store = build_vector_store(
        chunks, LexicalHashEmbeddings(dim=512), qdrant_path=None, lane="offline"
    )
    docs = [
        CorpusDocument(
            csv_row_id="000",
            doc_id="doc:000",
            text="본문",
            metadata={
                "project_name": PROJECT,
                "issuer": "한영대학",
                "budget_krw_int": 130_000_000,
                "bid_end_at_iso": "2024-10-15T17:00:00",
            },
        )
    ]
    return AgentRuntime(
        store=store,
        generator=TemplateAnswerGenerator(),
        router=RuleRouter(),
        rewriter=RuleQueryRewriter(),
        docs=docs,
        audit=AuditLogger(tmp_path / "audit.jsonl"),
        reports_dir=tmp_path / "reports",
        top_k=3,
        min_score=min_score,
        thread_id="t-test",
    )


def test_route_node_sets_route_and_original(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    out = rt.route_node({"question": f"{PROJECT} 사업 예산 알려줘"})
    assert out["route"] == "rag_query"
    assert out["original_question"] == f"{PROJECT} 사업 예산 알려줘"


def test_retrieve_and_grade_sufficient(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    out = rt.retrieve_node({"question": f"{PROJECT} 사업 예산 알려줘"})
    assert out["results"] and out["results"][0]["chunk_id"] == "doc:000:chunk:0"
    assert out["tool_calls"][0]["tool"] == "search_rfp"
    graded = rt.grade_node({"results": out["results"]})
    assert graded["grade"] == "sufficient"


def test_grade_branch_routes_by_count(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    assert rt.grade_branch({"grade": "sufficient"}) == "generate"
    assert rt.grade_branch({"grade": "insufficient", "rewrite_count": 0}) == "rewrite"
    assert rt.grade_branch({"grade": "insufficient", "rewrite_count": 2}) == "abstain"


def test_rewrite_node_increments_and_rewrites(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    out = rt.rewrite_node(
        {
            "original_question": "안녕하세요 혹시 한영대학교 예산 알려줘",
            "rewrite_count": 0,
        }
    )
    assert out["rewrite_count"] == 1
    assert "안녕하세요" not in out["question"]


def test_generate_and_verify_rag_path(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    retrieved = rt.retrieve_node({"question": f"{PROJECT} 사업 예산 알려줘"})
    state = {
        "route": "rag_query",
        "question": f"{PROJECT} 사업 예산 알려줘",
        "original_question": f"{PROJECT} 사업 예산 알려줘",
        "results": retrieved["results"],
    }
    gen = rt.generate_node(state)
    assert gen["answer"] is not None
    assert "130,000,000" in gen["answer"]["answer"]
    assert gen["answer"]["sources"][0]["chunk_id"] == "doc:000:chunk:0"
    verified = rt.verify_node({**state, **gen})
    assert verified["verify_ok"] is True


def test_generate_node_metadata_route_formats_tool_result(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    state = {
        "route": "metadata_query",
        "question": "사업 금액이 가장 큰 공고 1건은?",
        "original_question": "사업 금액이 가장 큰 공고 1건은?",
        "tool_args": {
            "sort_by": "budget_krw_int",
            "descending": True,
            "top_n": 1,
            "agg": "list",
        },
    }
    tool_out = rt.tool_exec_node(state)
    assert tool_out["tool_result"]["doc_ids"] == ["doc:000"]
    gen = rt.generate_node({**state, **tool_out})
    assert PROJECT in gen["answer"]["answer"]
    assert gen["answer"]["sources"][0]["doc_id"] == "doc:000"
    verified = rt.verify_node({**state, **tool_out, **gen})
    assert verified["verify_ok"] is True


def test_verify_branch_decisions(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    assert rt.verify_branch({"answer": None}) == "abstain"
    assert (
        rt.verify_branch(
            {"answer": {"x": 1}, "verify_ok": True, "save_requested": False}
        )
        == "respond"
    )
    assert (
        rt.verify_branch(
            {"answer": {"x": 1}, "verify_ok": True, "save_requested": True}
        )
        == "save_report"
    )
    assert rt.verify_branch({"answer": {"x": 1}, "verify_ok": False}) == "regenerate"
    assert (
        rt.verify_branch({"answer": {"x": 1}, "verify_ok": False, "regenerated": True})
        == "abstain"
    )


def test_abstain_node_uses_existing_contract(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    out = rt.abstain_node({"original_question": "화성 이주선 산소탱크?", "results": []})
    assert "없는 정보" in out["answer"]["answer"]
    assert "insufficient_context" in out["answer"]["warnings"]
    assert out["outcome"] == "abstained"
