from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_qdrant import QdrantVectorStore

from .index_store import SearchResult
from .providers import (
    AnswerGenerator,
    build_embeddings,
    build_generator,
    chunk_context_block,
    normalize_lane,
)
from .vector_index import RETRIEVAL_VECTOR, load_vector_store, search

ABSTAIN_ANSWER = "검색된 제안요청서 근거만으로는 답할 수 없는 정보입니다. 없는 정보"

DEFAULT_MIN_SCORE = 0.05


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
    min_score: float = DEFAULT_MIN_SCORE,
    *,
    retrieval_mode: str = RETRIEVAL_VECTOR,
    index_dir: Path | None = None,
) -> dict[str, Any]:
    results = search(
        store,
        query,
        top_k=top_k,
        retrieval_mode=retrieval_mode,
        index_dir=index_dir,
    )
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
        # source_texts feed the RAGAS judge as retrieved_contexts and MUST match
        # what build_answer_prompt showed the generator (metadata lines + body),
        # otherwise metadata-grounded answers get judged unfaithful.
        "source_texts": [chunk_context_block(r) for r in results],
        "warnings": [],
        "confidence": "high" if top_score >= 2 * min_score else "medium",
        "retrieved_doc_ids": [r.doc_id for r in results],
        "retrieved_chunk_ids": [r.chunk_id for r in results],
        "scores": [r.score for r in results],
    }


def _load_manifest(index_dir: Path) -> dict[str, Any]:
    manifest_path = index_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"index manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def answer_query(
    index_dir: Path | str,
    query: str,
    top_k: int = 5,
    min_score: float = DEFAULT_MIN_SCORE,
    provider: str | None = None,
    *,
    retrieval_mode: str = RETRIEVAL_VECTOR,
) -> dict[str, Any]:
    index_dir = Path(index_dir)
    manifest = _load_manifest(index_dir)
    index_lane = normalize_lane(manifest.get("embedding_provider", "offline"))
    lane = normalize_lane(provider) if provider else index_lane
    if lane != index_lane:
        raise ValueError(
            f"provider lane {lane!r} does not match index embedding lane {index_lane!r}; rebuild the index"
        )
    embeddings = build_embeddings(lane)
    store = load_vector_store(index_dir / "qdrant", embeddings, lane=lane)
    generator = build_generator(lane)
    return answer_with_store(
        store,
        generator,
        query,
        top_k=top_k,
        min_score=min_score,
        retrieval_mode=retrieval_mode,
        index_dir=index_dir,
    )
