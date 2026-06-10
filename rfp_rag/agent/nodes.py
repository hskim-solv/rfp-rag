from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_qdrant import QdrantVectorStore
from langgraph.types import interrupt

from ..corpus import CorpusDocument
from ..index_store import SearchResult
from ..providers import AnswerGenerator, chunk_context_block
from ..rag_chain import DEFAULT_MIN_SCORE, _source_from_result, abstention_response
from ..vector_index import search
from .brains import QueryRewriter, Router
from .state import (
    OUTCOME_ABSTAINED,
    OUTCOME_ANSWERED,
    OUTCOME_REJECTED,
    AgentState,
    dict_to_result,
    result_to_dict,
)
from .tools import AuditLogger, aggregate_metadata, save_report_file


@dataclass
class AgentRuntime:
    """그래프 노드 묶음. 레인별 차이는 generator/router/rewriter 주입으로만 갈라진다."""

    store: QdrantVectorStore
    generator: AnswerGenerator
    router: Router
    rewriter: QueryRewriter
    docs: list[CorpusDocument]
    audit: AuditLogger
    reports_dir: Path
    top_k: int = 5
    min_score: float = DEFAULT_MIN_SCORE
    max_rewrites: int = 2
    thread_id: str = "default"

    # --- nodes -------------------------------------------------------------

    def route_node(self, state: AgentState) -> dict[str, Any]:
        question = state["question"]
        decision = self.router.route(question)
        return {
            "route": decision.route,
            "save_requested": decision.save_requested,
            "tool_args": decision.tool_args,
            "original_question": state.get("original_question") or question,
        }

    def retrieve_node(self, state: AgentState) -> dict[str, Any]:
        query = state["question"]
        results = search(self.store, query, top_k=self.top_k)
        call = {"tool": "search_rfp", "args": {"query": query, "top_k": self.top_k}}
        self.audit.record(
            thread_id=self.thread_id,
            tool="search_rfp",
            args=call["args"],
            outcome=f"{len(results)} results",
        )
        return {"results": [result_to_dict(r) for r in results], "tool_calls": [call]}

    def grade_node(self, state: AgentState) -> dict[str, Any]:
        results = state.get("results") or []
        ok = bool(results) and results[0]["score"] >= self.min_score
        return {"grade": "sufficient" if ok else "insufficient"}

    def grade_branch(self, state: AgentState) -> str:
        if state["grade"] == "sufficient":
            return "generate"
        if state.get("rewrite_count", 0) < self.max_rewrites:
            return "rewrite"
        return "abstain"

    def rewrite_node(self, state: AgentState) -> dict[str, Any]:
        attempt = state.get("rewrite_count", 0) + 1
        new_q = self.rewriter.rewrite(state["original_question"], attempt)
        return {"question": new_q, "rewrite_count": attempt}

    def tool_exec_node(self, state: AgentState) -> dict[str, Any]:
        args = state.get("tool_args") or {}
        try:
            result: dict[str, Any] = aggregate_metadata(self.docs, **args)
            outcome = "ok"
        except (ValueError, TypeError) as exc:
            result = {"error": str(exc)}
            outcome = f"error: {exc}"
        call = {"tool": "aggregate_metadata", "args": args, "outcome": outcome}
        self.audit.record(thread_id=self.thread_id, tool="aggregate_metadata", args=args, outcome=outcome)
        return {"tool_result": result, "tool_calls": [call]}

    def generate_node(self, state: AgentState) -> dict[str, Any]:
        if state["route"] == "metadata_query":
            return {"answer": self._metadata_answer(state)}
        results = [dict_to_result(d) for d in state.get("results") or []]
        text = self.generator.generate(state["question"], results)
        if "없는 정보" in text:
            return {"answer": None}
        return {"answer": self._rag_answer(state, text, results)}

    def regenerate_node(self, state: AgentState) -> dict[str, Any]:
        return {"regenerated": True}

    def verify_node(self, state: AgentState) -> dict[str, Any]:
        answer = state.get("answer")
        if answer is None:
            return {"verify_ok": False}
        if state["route"] == "metadata_query":
            # 결정론 조립 경로 — 인용 검증은 rag 경로 대상
            return {"verify_ok": "error" not in (state.get("tool_result") or {})}
        cited = {s["chunk_id"] for s in answer["sources"]}
        retrieved = set(answer["retrieved_chunk_ids"])
        return {"verify_ok": bool(cited) and cited <= retrieved}

    def verify_branch(self, state: AgentState) -> str:
        if state.get("answer") is None:
            return "abstain"
        if state.get("verify_ok"):
            return "save_report" if state.get("save_requested") else "respond"
        if not state.get("regenerated"):
            return "regenerate"
        return "abstain"

    def abstain_node(self, state: AgentState) -> dict[str, Any]:
        results = [dict_to_result(d) for d in state.get("results") or []]
        return {
            "answer": abstention_response(state["original_question"], results),
            "outcome": OUTCOME_ABSTAINED,
        }

    def save_report_node(self, state: AgentState) -> dict[str, Any]:
        filename = f"agent_report_{self.thread_id}.md"
        content = self._render_report(state)
        decision = interrupt(
            {
                "action": "save_report",
                "filename": filename,
                "preview": content[:500],
                "message": "보고서를 저장할까요? --approve 또는 --reject로 재개하세요.",
            }
        )
        approved = decision == "approve" or (isinstance(decision, dict) and decision.get("action") == "approve")
        args = {"filename": filename}
        if approved:
            path = save_report_file(self.reports_dir, filename, content)
            self.audit.record(
                thread_id=self.thread_id, tool="save_report", args=args, outcome=str(path), approved=True
            )
            answer = dict(state["answer"] or {})
            answer["report_path"] = str(path)
            return {
                "answer": answer,
                "outcome": OUTCOME_ANSWERED,
                "tool_calls": [{"tool": "save_report", "args": args, "outcome": str(path)}],
            }
        self.audit.record(
            thread_id=self.thread_id, tool="save_report", args=args, outcome="rejected", approved=False
        )
        return {
            "outcome": OUTCOME_REJECTED,
            "tool_calls": [{"tool": "save_report", "args": args, "outcome": "rejected"}],
        }

    def respond_node(self, state: AgentState) -> dict[str, Any]:
        if state.get("outcome"):
            return {}
        return {"outcome": OUTCOME_ANSWERED}

    # --- helpers -----------------------------------------------------------

    def _rag_answer(self, state: AgentState, text: str, results: list[SearchResult]) -> dict[str, Any]:
        top_score = results[0].score
        return {
            "query": state["original_question"],
            "answer": text,
            "sources": [_source_from_result(r) for r in results],
            "source_texts": [chunk_context_block(r) for r in results],
            "warnings": [],
            "confidence": "high" if top_score >= 2 * self.min_score else "medium",
            "retrieved_doc_ids": [r.doc_id for r in results],
            "retrieved_chunk_ids": [r.chunk_id for r in results],
            "scores": [r.score for r in results],
        }

    def _metadata_answer(self, state: AgentState) -> dict[str, Any] | None:
        tr = state.get("tool_result") or {}
        if "error" in tr:
            return None
        if tr.get("agg") == "count":
            text = f"조건에 해당하는 공고는 총 {tr['count']}건입니다."
        elif tr.get("agg") == "sum":
            text = f"조건에 해당하는 공고 {tr['count']}건의 사업 금액 합계는 {tr['sum']:,}원입니다."
        else:
            lines = [
                f"{i}. {r['project_name']} (발주: {r['issuer']}, 금액: "
                f"{(r['budget_krw_int'] or 0):,}원, 마감: {r['bid_end_at_iso'] or '미상'})"
                for i, r in enumerate(tr.get("rows") or [], start=1)
            ]
            if not lines:
                return None
            text = "조건에 해당하는 공고 목록입니다.\n" + "\n".join(lines)
        sources = [
            {
                "doc_id": r["doc_id"],
                "chunk_id": "",
                "score": None,
                "csv_row_id": r["csv_row_id"],
                "project_name": r["project_name"],
                "issuer": r["issuer"],
                "filename": "",
            }
            for r in tr.get("rows") or []
        ]
        return {
            "query": state["original_question"],
            "answer": text,
            "sources": sources,
            "source_texts": [],
            "warnings": [],
            "confidence": "high",
            "retrieved_doc_ids": tr.get("doc_ids") or [],
            "retrieved_chunk_ids": [],
            "scores": [],
            "tool_result": tr,
        }

    def _render_report(self, state: AgentState) -> str:
        answer = state.get("answer") or {}
        lines = [
            "# RFP Agent 보고서",
            "",
            f"- 질문: {state.get('original_question', '')}",
            f"- 경로: {state.get('route', '')}",
            f"- thread: {self.thread_id}",
            "",
            "## 답변",
            "",
            str(answer.get("answer", "")),
        ]
        if answer.get("sources"):
            lines += ["", "## 근거"]
            lines += [
                f"- {s.get('doc_id')} {s.get('project_name', '')} ({s.get('issuer', '')})"
                for s in answer["sources"]
            ]
        return "\n".join(lines) + "\n"
