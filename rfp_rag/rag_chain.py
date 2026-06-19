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
from .rerank import RERANKER_NONE, Reranker, build_reranker
from .vector_index import RETRIEVAL_VECTOR, load_vector_store, search
from .visual_sidecar import (
    VisualEvidenceIndex,
    attach_visual_evidence,
    load_visual_sidecar,
)

ABSTAIN_ANSWER = "검색된 제안요청서 근거만으로는 답할 수 없는 정보입니다. 없는 정보"

# Section-aware source-first offline retrieval is calibrated at 0.34; callers can lower this
# explicitly for focused unit tests or lane-specific experiments.
DEFAULT_MIN_SCORE = 0.34


class AnswerStageError(RuntimeError):
    def __init__(self, stage: str, original: Exception) -> None:
        super().__init__(str(original))
        self.stage = stage
        self.original = original
        self.__cause__ = original


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
        "section_title": md.get("section_title"),
        "section_type": md.get("section_type"),
        "section_path": md.get("section_path") or [],
        "page_start": md.get("section_page_start"),
        "page_end": md.get("section_page_end"),
        "visual_evidence": md.get("visual_evidence") or [],
    }


def _reranker_scores(results: list[SearchResult]) -> list[Any]:
    return [
        result.metadata.get("reranker_score")
        for result in results
        if "reranker_score" in result.metadata
    ]


def abstention_response(
    query: str,
    results: list[SearchResult],
    *,
    reranker: str = RERANKER_NONE,
    rerank_candidate_k: int | None = None,
    preserve_sources: bool = False,
) -> dict[str, Any]:
    return {
        "query": query,
        "answer": ABSTAIN_ANSWER,
        "sources": [_source_from_result(r) for r in results]
        if preserve_sources
        else [],
        "source_texts": [chunk_context_block(r) for r in results]
        if preserve_sources
        else [],
        "warnings": ["insufficient_context"],
        "confidence": "low",
        "retrieved_doc_ids": [r.doc_id for r in results],
        "retrieved_chunk_ids": [r.chunk_id for r in results],
        "scores": [r.score for r in results],
        "reranker": reranker,
        "rerank_candidate_k": rerank_candidate_k,
        "reranker_scores": _reranker_scores(results),
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
    reranker: Reranker | None = None,
    rerank_candidate_k: int | None = None,
    visual_evidence_index: VisualEvidenceIndex | None = None,
    preserve_generator_abstention_sources: bool = False,
) -> dict[str, Any]:
    candidate_k = max(top_k, rerank_candidate_k or top_k)
    reranker_name = reranker.name if reranker else RERANKER_NONE
    try:
        results = search(
            store,
            query,
            top_k=candidate_k,
            retrieval_mode=retrieval_mode,
            index_dir=index_dir,
        )
    except ValueError:
        raise
    except Exception as exc:
        raise AnswerStageError("retrieval", exc) from exc
    if not results or results[0].score < min_score:
        return abstention_response(
            query,
            results,
            reranker=reranker_name,
            rerank_candidate_k=candidate_k,
        )
    if reranker is not None:
        try:
            results = reranker.rerank(query, results, top_k=top_k)
        except Exception as exc:
            raise AnswerStageError("rerank", exc) from exc
    else:
        results = results[:top_k]
    results = attach_visual_evidence(results, visual_evidence_index)

    try:
        answer = generator.generate(query, results)
    except Exception as exc:
        raise AnswerStageError("generation", exc) from exc
    # "없는 정보" is the abstention sentinel produced by generators (e.g.
    # LLMAnswerGenerator on insufficient_context). A grounded answer merely
    # quoting this phrase is a known, accepted false-abstain risk.
    if "없는 정보" in answer:
        return abstention_response(
            query,
            results,
            reranker=reranker_name,
            rerank_candidate_k=candidate_k,
            preserve_sources=preserve_generator_abstention_sources,
        )

    top_score = results[0].score
    return {
        "query": query,
        "answer": answer,
        "sources": [_source_from_result(r) for r in results],
        # source_texts feed the LLM judge as retrieved_contexts and MUST match
        # what build_answer_prompt showed the generator (metadata lines + body),
        # otherwise metadata-grounded answers get judged unfaithful.
        "source_texts": [chunk_context_block(r) for r in results],
        "warnings": [],
        "confidence": "high" if top_score >= 2 * min_score else "medium",
        "retrieved_doc_ids": [r.doc_id for r in results],
        "retrieved_chunk_ids": [r.chunk_id for r in results],
        "scores": [r.score for r in results],
        "reranker": reranker_name,
        "rerank_candidate_k": candidate_k,
        "reranker_scores": _reranker_scores(results),
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
    reranker: str = RERANKER_NONE,
    rerank_candidate_k: int | None = None,
    visual_candidate_path: Path | str | None = None,
    visual_gate_path: Path | str | None = None,
    preserve_generator_abstention_sources: bool = False,
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
    reranker_impl = build_reranker(lane, reranker)
    visual_evidence_index = (
        load_visual_sidecar(visual_candidate_path, visual_gate_path)
        if visual_candidate_path is not None
        else None
    )
    return answer_with_store(
        store,
        generator,
        query,
        top_k=top_k,
        min_score=min_score,
        retrieval_mode=retrieval_mode,
        index_dir=index_dir,
        reranker=reranker_impl,
        rerank_candidate_k=rerank_candidate_k,
        visual_evidence_index=visual_evidence_index,
        preserve_generator_abstention_sources=preserve_generator_abstention_sources,
    )
