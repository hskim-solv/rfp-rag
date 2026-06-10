from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .chunking import Chunk
from .fake_provider import cosine_score, lexical_features, normalize_text


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    doc_id: str
    csv_row_id: str
    score: float
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class LocalIndex:
    manifest: dict[str, Any]
    chunks: list[Chunk]


def chunk_to_record(chunk: Chunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "csv_row_id": chunk.csv_row_id,
        "text": chunk.text,
        "metadata": chunk.metadata,
    }


def chunk_from_record(record: dict[str, Any]) -> Chunk:
    return Chunk(
        chunk_id=record["chunk_id"],
        doc_id=record["doc_id"],
        csv_row_id=record["csv_row_id"],
        text=record.get("text", ""),
        metadata=dict(record.get("metadata", {})),
    )


def save_index(out_dir: Path, manifest: dict[str, Any], chunks: Iterable[Chunk]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk_to_record(chunk), ensure_ascii=False, sort_keys=True) + "\n")


def load_index(index_dir: Path | str) -> LocalIndex:
    index_dir = Path(index_dir)
    manifest = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
    chunks = [chunk_from_record(json.loads(line)) for line in (index_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return LocalIndex(manifest=manifest, chunks=chunks)


def _search_text(chunk: Chunk) -> str:
    md = chunk.metadata
    parts = [
        chunk.text,
        str(md.get("project_name", "")),
        str(md.get("issuer", "")),
        str(md.get("summary", "")),
        str(md.get("csv_filename_raw", "")),
        str(md.get("공고 번호", "")),
    ]
    return "\n".join(part for part in parts if part)


def retrieve(index: LocalIndex, query: str, top_k: int = 5) -> list[SearchResult]:
    if top_k <= 0:
        return []
    query_features = lexical_features(query)
    normalized_query = normalize_text(query)
    scored: list[SearchResult] = []
    for chunk in index.chunks:
        search_text = _search_text(chunk)
        score = cosine_score(query_features, lexical_features(search_text))
        # Exact substring bonus keeps deterministic smoke retrieval stable for project names.
        if normalized_query and normalized_query in normalize_text(search_text):
            score += 1.0
        if score <= 0:
            continue
        scored.append(
            SearchResult(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                csv_row_id=chunk.csv_row_id,
                score=round(score, 8),
                text=chunk.text,
                metadata=chunk.metadata,
            )
        )
    scored.sort(key=lambda item: (-item.score, item.doc_id, item.chunk_id))
    return scored[:top_k]
