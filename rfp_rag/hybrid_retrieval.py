from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .index_store import SearchResult

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in _TOKEN_RE.finditer(text)]


def _embedding_style_text(text: str, metadata: dict[str, Any]) -> str:
    header = f"사업명: {metadata.get('project_name', '')}\n발주기관: {metadata.get('issuer', '')}"
    return f"{header}\n{text}" if text else header


def load_chunk_results(index_dir: Path | str) -> list[SearchResult]:
    chunks_path = Path(index_dir) / "chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"chunks file not found: {chunks_path}")

    results: list[SearchResult] = []
    with chunks_path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            metadata = dict(record.get("metadata") or {})
            text = _embedding_style_text(record.get("text", ""), metadata)
            results.append(
                SearchResult(
                    chunk_id=record["chunk_id"],
                    doc_id=record["doc_id"],
                    csv_row_id=record["csv_row_id"],
                    score=0.0,
                    text=text,
                    metadata=metadata,
                )
            )
    return results


@dataclass(frozen=True)
class _DocStats:
    result: SearchResult
    term_counts: Counter[str]
    length: int


class BM25Index:
    def __init__(self, documents: list[SearchResult], *, k1: float = 1.5, b: float = 0.75) -> None:
        self._documents = documents
        self._k1 = k1
        self._b = b
        self._stats: list[_DocStats] = []
        self._document_frequency: Counter[str] = Counter()

        total_length = 0
        for document in documents:
            terms = tokenize(document.text)
            term_counts = Counter(terms)
            self._stats.append(_DocStats(document, term_counts, len(terms)))
            self._document_frequency.update(term_counts.keys())
            total_length += len(terms)
        self._avgdl = total_length / len(documents) if documents else 0.0

    @classmethod
    def from_index_dir(cls, index_dir: Path | str) -> BM25Index:
        return cls(load_chunk_results(index_dir))

    def _idf(self, term: str) -> float:
        n_docs = len(self._stats)
        if n_docs == 0:
            return 0.0
        df = self._document_frequency.get(term, 0)
        return math.log(1 + (n_docs - df + 0.5) / (df + 0.5))

    def _score(self, query_terms: list[str], stats: _DocStats) -> float:
        if not query_terms or stats.length == 0 or self._avgdl == 0:
            return 0.0

        score = 0.0
        for term in query_terms:
            tf = stats.term_counts.get(term, 0)
            if tf == 0:
                continue
            denominator = tf + self._k1 * (1 - self._b + self._b * stats.length / self._avgdl)
            score += self._idf(term) * ((tf * (self._k1 + 1)) / denominator)
        return score

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        if top_k <= 0:
            return []
        query_terms = tokenize(query)
        if not query_terms:
            return []

        scored: list[SearchResult] = []
        for stats in self._stats:
            score = self._score(query_terms, stats)
            if score <= 0:
                continue
            scored.append(
                SearchResult(
                    chunk_id=stats.result.chunk_id,
                    doc_id=stats.result.doc_id,
                    csv_row_id=stats.result.csv_row_id,
                    score=round(score, 8),
                    text=stats.result.text,
                    metadata=stats.result.metadata,
                )
            )
        scored.sort(key=lambda item: (-item.score, item.doc_id, item.chunk_id))
        return scored[:top_k]


def fuse_ranked_results(
    vector_results: list[SearchResult],
    bm25_results: list[SearchResult],
    *,
    top_k: int,
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3,
    rank_constant: int = 60,
) -> list[SearchResult]:
    if top_k <= 0:
        return []

    by_chunk: dict[str, SearchResult] = {}
    scores: dict[str, float] = {}

    def add(results: list[SearchResult], weight: float) -> None:
        for rank, result in enumerate(results, start=1):
            by_chunk.setdefault(result.chunk_id, result)
            scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + weight / (rank_constant + rank)

    add(vector_results, vector_weight)
    add(bm25_results, bm25_weight)

    fused: list[SearchResult] = []
    for chunk_id, score in scores.items():
        base = by_chunk[chunk_id]
        fused.append(
            SearchResult(
                chunk_id=base.chunk_id,
                doc_id=base.doc_id,
                csv_row_id=base.csv_row_id,
                score=round(score, 8),
                text=base.text,
                metadata=base.metadata,
            )
        )
    fused.sort(key=lambda item: (-item.score, item.doc_id, item.chunk_id))
    return fused[:top_k]
