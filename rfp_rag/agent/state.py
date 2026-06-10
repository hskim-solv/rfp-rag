from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from ..index_store import SearchResult

RouteKind = Literal["rag_query", "metadata_query"]

OUTCOME_ANSWERED = "answered"
OUTCOME_ABSTAINED = "abstained"
OUTCOME_REJECTED = "rejected"


class AgentState(TypedDict, total=False):
    question: str                       # 현재(재작성 반영) 질의
    original_question: str
    route: RouteKind
    save_requested: bool
    tool_args: dict[str, Any]           # metadata_query 도구 인자 (router가 추출)
    results: list[dict[str, Any]]       # SearchResult 직렬화 (checkpointer 호환)
    grade: str                          # sufficient | insufficient
    rewrite_count: int
    regenerated: bool
    verify_ok: bool
    tool_result: dict[str, Any] | None  # aggregate_metadata 결과
    answer: dict[str, Any] | None       # 기존 응답 JSON 스키마 (+ agent 확장 필드)
    outcome: str                        # answered | abstained | rejected
    tool_calls: Annotated[list[dict[str, Any]], operator.add]  # audit용 누적


def result_to_dict(r: SearchResult) -> dict[str, Any]:
    return {
        "chunk_id": r.chunk_id,
        "doc_id": r.doc_id,
        "csv_row_id": r.csv_row_id,
        "score": r.score,
        "text": r.text,
        "metadata": r.metadata,
    }


def dict_to_result(d: dict[str, Any]) -> SearchResult:
    return SearchResult(
        chunk_id=d["chunk_id"],
        doc_id=d["doc_id"],
        csv_row_id=d["csv_row_id"],
        score=d["score"],
        text=d["text"],
        metadata=d["metadata"],
    )
