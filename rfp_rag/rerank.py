from __future__ import annotations

import json
import os
from typing import Callable, Protocol

from pydantic import BaseModel, Field

from .index_store import SearchResult
from .providers import (
    DEFAULT_OPEN_BASE_URL,
    DEFAULT_OPEN_MODEL,
    LANE_OFFLINE,
    LANE_OPEN,
    LANE_REAL_OPENAI,
    _open_api_key,
    chunk_context_block,
    normalize_lane,
    require_openai_key,
)
from .tracing import tracing_callbacks

RERANKER_NONE = "none"
RERANKER_LLM = "llm"
RERANKERS = {RERANKER_NONE, RERANKER_LLM}


class Reranker(Protocol):
    name: str

    def rerank(
        self, query: str, results: list[SearchResult], top_k: int
    ) -> list[SearchResult]: ...


class LLMRerankRank(BaseModel):
    chunk_id: str = Field(description="Candidate chunk_id to keep")
    relevance_score: float = Field(ge=0.0, le=1.0)


class LLMRerankOutput(BaseModel):
    ranks: list[LLMRerankRank] = Field(
        default_factory=list,
        description="Ordered candidates from most to least relevant",
    )


def _render_rerank_prompt(query: str, results: list[SearchResult]) -> str:
    candidates = [
        {
            "rank": idx,
            "chunk_id": result.chunk_id,
            "retrieval_score": result.score,
            "context": chunk_context_block(result),
        }
        for idx, result in enumerate(results, start=1)
    ]
    return (
        "You are reranking Korean public RFP evidence chunks for a RAG system.\n"
        "Return only chunks that are directly useful for answering the query.\n"
        "Keep exact section/page evidence if the query asks for a section.\n"
        "Assign relevance_score from 0.0 to 1.0.\n\n"
        f"Query:\n{query}\n\n"
        f"Candidate chunks JSON:\n{json.dumps(candidates, ensure_ascii=False)}"
    )


def _real_openai_invoke(prompt: str) -> LLMRerankOutput:
    from langchain_openai import ChatOpenAI

    model = os.environ.get("RFP_RERANK_MODEL") or os.environ.get(
        "RFP_GENERATION_MODEL", "gpt-5.4-mini"
    )
    llm = ChatOpenAI(model=model, callbacks=tracing_callbacks()).with_structured_output(
        LLMRerankOutput
    )
    return llm.invoke(
        [
            (
                "system",
                "Rank RFP evidence chunks. Return structured ranks only.",
            ),
            ("human", prompt),
        ]
    )


def _open_invoke(prompt: str) -> LLMRerankOutput:
    from langchain_openai import ChatOpenAI

    base_url = os.environ.get("RFP_RERANK_BASE_URL") or os.environ.get(
        "RFP_OPEN_BASE_URL", DEFAULT_OPEN_BASE_URL
    )
    model = os.environ.get("RFP_RERANK_MODEL") or os.environ.get(
        "RFP_OPEN_MODEL", DEFAULT_OPEN_MODEL
    )
    llm = ChatOpenAI(
        model=model,
        base_url=base_url,
        api_key=_open_api_key(base_url),
        callbacks=tracing_callbacks(),
        extra_body={"thinking": {"type": "disabled"}},
    ).with_structured_output(LLMRerankOutput, method="function_calling")
    return llm.invoke(
        [
            (
                "system",
                "Rank RFP evidence chunks. Return structured ranks only.",
            ),
            ("human", prompt),
        ]
    )


class LLMReranker:
    name = RERANKER_LLM

    def __init__(self, invoke: Callable[[str], LLMRerankOutput]) -> None:
        self._invoke = invoke

    def rerank(
        self, query: str, results: list[SearchResult], top_k: int
    ) -> list[SearchResult]:
        if top_k <= 0:
            return []
        if not results:
            return []
        output = self._invoke(_render_rerank_prompt(query, results))
        by_chunk = {result.chunk_id: result for result in results}
        reranked: list[SearchResult] = []
        seen: set[str] = set()
        for rank in output.ranks:
            result = by_chunk.get(rank.chunk_id)
            if result is None or result.chunk_id in seen:
                continue
            seen.add(result.chunk_id)
            metadata = dict(result.metadata)
            metadata.update(
                {
                    "reranker": self.name,
                    "reranker_score": round(float(rank.relevance_score), 8),
                    "pre_rerank_score": result.score,
                }
            )
            reranked.append(
                SearchResult(
                    chunk_id=result.chunk_id,
                    doc_id=result.doc_id,
                    csv_row_id=result.csv_row_id,
                    score=result.score,
                    text=result.text,
                    metadata=metadata,
                )
            )
        if not reranked:
            return results[:top_k]
        for result in results:
            if len(reranked) >= top_k:
                break
            if result.chunk_id in seen:
                continue
            reranked.append(result)
        return reranked[:top_k]


def build_reranker(lane: str, reranker: str = RERANKER_NONE) -> Reranker | None:
    if reranker not in RERANKERS:
        raise ValueError(f"unknown reranker: {reranker!r}")
    if reranker == RERANKER_NONE:
        return None

    lane = normalize_lane(lane)
    if lane == LANE_OFFLINE:
        raise ValueError("LLM reranker requires real_openai or open lane")
    if lane == LANE_OPEN:
        _open_api_key(
            os.environ.get("RFP_RERANK_BASE_URL")
            or os.environ.get("RFP_OPEN_BASE_URL", DEFAULT_OPEN_BASE_URL)
        )
        return LLMReranker(_open_invoke)
    if lane == LANE_REAL_OPENAI:
        require_openai_key()
        return LLMReranker(_real_openai_invoke)
    raise ValueError(f"unsupported reranker lane: {lane}")
