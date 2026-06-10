from __future__ import annotations

import json
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from rfp_rag.agent.brains import RuleQueryRewriter, RuleRouter
from rfp_rag.agent.graph import build_agent_graph, initial_state, run_config
from rfp_rag.agent.nodes import AgentRuntime
from rfp_rag.agent.tools import AuditLogger
from rfp_rag.chunking import Chunk
from rfp_rag.corpus import CorpusDocument
from rfp_rag.providers import LexicalHashEmbeddings, TemplateAnswerGenerator
from rfp_rag.vector_index import build_vector_store

PROJECT = "한영대학교 트랙운영 학사정보시스템 고도화"
NOISY_PREFIX = (
    "안녕하세요 혹시 다른 건 말고 그게 궁금한데요 그러면 근데 그런데 아니면 "
    "혹은 그리고 좀 대해서 관련해서 궁금한데 있을까요 "
)


def _runtime(tmp_path: Path, min_score: float = 0.05, thread_id: str = "t-graph") -> AgentRuntime:
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
    store = build_vector_store(chunks, LexicalHashEmbeddings(dim=512), qdrant_path=None, lane="offline")
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
        thread_id=thread_id,
    )


def test_direct_rag_path_answers(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    graph = build_agent_graph(rt)
    out = graph.invoke(initial_state(f"{PROJECT} 사업 예산 알려줘"), run_config("t1"))
    assert out["outcome"] == "answered"
    assert "130,000,000" in out["answer"]["answer"]
    assert out["rewrite_count"] == 0


def test_rewrite_recovers_noisy_question(tmp_path: Path) -> None:
    # 실측(결정론): clean 0.787 / noisy 0.422 / rewrite1 0.842 — 0.45가 noisy만 걸러낸다
    rt = _runtime(tmp_path, min_score=0.45)
    graph = build_agent_graph(rt)
    noisy = NOISY_PREFIX + f"{PROJECT} 사업 예산 알려줘"
    # 전제 검증: 노이즈 질의는 min_score 미달이어야 rewrite가 트리거된다
    from rfp_rag.vector_index import search

    assert search(rt.store, noisy, top_k=1)[0].score < 0.45
    out = graph.invoke(initial_state(noisy), run_config("t2"))
    assert out["outcome"] == "answered"
    assert out["rewrite_count"] >= 1
    assert "130,000,000" in out["answer"]["answer"]


def test_exhausted_rewrites_abstain(tmp_path: Path) -> None:
    rt = _runtime(tmp_path, min_score=0.05)
    graph = build_agent_graph(rt)
    out = graph.invoke(initial_state("화성 이주선 산소탱크 발사일은 언제야?"), run_config("t3"))
    assert out["outcome"] == "abstained"
    assert out["rewrite_count"] == 2  # 루프 종료 보장
    assert "없는 정보" in out["answer"]["answer"]
    assert "insufficient_context" in out["answer"]["warnings"]


def test_metadata_route_end_to_end(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    graph = build_agent_graph(rt)
    out = graph.invoke(initial_state("사업 금액이 가장 큰 공고 1건은?"), run_config("t4"))
    assert out["outcome"] == "answered"
    assert out["route"] == "metadata_query"
    assert out["tool_result"]["doc_ids"] == ["doc:000"]
    assert PROJECT in out["answer"]["answer"]


def test_hitl_approve_saves_report_and_audits(tmp_path: Path) -> None:
    rt = _runtime(tmp_path, thread_id="t5")
    graph = build_agent_graph(rt, checkpointer=MemorySaver())
    q = f"{PROJECT} 사업을 요약해서 보고서로 저장해줘"
    first = graph.invoke(initial_state(q), run_config("t5"))
    assert "__interrupt__" in first  # 승인 대기
    payload = first["__interrupt__"][0].value
    assert payload["action"] == "save_report"
    resumed = graph.invoke(Command(resume="approve"), run_config("t5"))
    assert resumed["outcome"] == "answered"
    report = Path(resumed["answer"]["report_path"])
    assert report.exists() and report.parent == (tmp_path / "reports").resolve()
    audit = [json.loads(l) for l in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    save_entries = [e for e in audit if e["tool"] == "save_report"]
    assert save_entries and save_entries[-1]["approved"] is True


def test_hitl_reject_skips_save_and_audits(tmp_path: Path) -> None:
    rt = _runtime(tmp_path, thread_id="t6")
    graph = build_agent_graph(rt, checkpointer=MemorySaver())
    q = f"{PROJECT} 사업을 요약해서 보고서로 저장해줘"
    first = graph.invoke(initial_state(q), run_config("t6"))
    assert "__interrupt__" in first
    resumed = graph.invoke(Command(resume="reject"), run_config("t6"))
    assert resumed["outcome"] == "rejected"
    assert not (tmp_path / "reports").exists() or not list((tmp_path / "reports").iterdir())
    audit = [json.loads(l) for l in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    save_entries = [e for e in audit if e["tool"] == "save_report"]
    assert save_entries and save_entries[-1]["approved"] is False
