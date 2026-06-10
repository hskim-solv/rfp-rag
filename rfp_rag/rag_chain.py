from __future__ import annotations

from typing import Any

from langchain_qdrant import QdrantVectorStore

from .index_store import SearchResult
from .providers import AnswerGenerator
from .vector_index import search

ABSTAIN_ANSWER = "검색된 제안요청서 근거만으로는 답할 수 없는 정보입니다. 없는 정보"


def _source_from_result(result: SearchResult) -> dict[str, Any]:
    md = result.metadata
    return {
        "doc_id": result.doc_id,
        "chunk_id": result.chunk_id,
        "score": result.score,
        "csv_row_id": result.csv_row_id,
        "project_name": md.get("project_name", ""),
        "issuer": md.get("issuer", ""),
        "filename": md.get("csv_filename_raw", ""),
    }


def abstention_response(query: str, results: list[SearchResult]) -> dict[str, Any]:
    return {
        "query": query,
        "answer": ABSTAIN_ANSWER,
        "sources": [],
        "source_texts": [],
        "warnings": ["insufficient_context"],
        "confidence": "low",
        "retrieved_doc_ids": [r.doc_id for r in results],
        "retrieved_chunk_ids": [r.chunk_id for r in results],
        "scores": [r.score for r in results],
    }


def answer_with_store(
    store: QdrantVectorStore,
    generator: AnswerGenerator,
    query: str,
    top_k: int = 5,
    min_score: float = 0.05,
) -> dict[str, Any]:
    results = search(store, query, top_k=top_k)
    if not results or results[0].score < min_score:
        return abstention_response(query, results)

    answer = generator.generate(query, results)
    # "없는 정보" is the abstention sentinel produced by generators (e.g.
    # LLMAnswerGenerator on insufficient_context). A grounded answer merely
    # quoting this phrase is a known, accepted false-abstain risk.
    if "없는 정보" in answer:
        return abstention_response(query, results)

    top_score = results[0].score
    return {
        "query": query,
        "answer": answer,
        "sources": [_source_from_result(r) for r in results],
        "source_texts": [r.text for r in results],
        "warnings": [],
        "confidence": "high" if top_score >= 2 * min_score else "medium",
        "retrieved_doc_ids": [r.doc_id for r in results],
        "retrieved_chunk_ids": [r.chunk_id for r in results],
        "scores": [r.score for r in results],
    }
