from __future__ import annotations

import json
import shutil
import uuid
from functools import lru_cache
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from .chunking import Chunk
from .hybrid_retrieval import BM25Index
from .index_store import SearchResult

_COLLECTION_PREFIX = "rfp_chunks"

RETRIEVAL_VECTOR = "vector"
RETRIEVAL_HYBRID = "hybrid"
RETRIEVAL_MODES = {RETRIEVAL_VECTOR, RETRIEVAL_HYBRID}


def collection_name(lane: str) -> str:
    return f"{_COLLECTION_PREFIX}_{lane}"


def embedding_text(chunk: Chunk) -> str:
    """Prepend key metadata so metadata-style questions retrieve well."""
    md = chunk.metadata
    lines = [
        f"사업명: {md.get('project_name', '')}",
        f"발주기관: {md.get('issuer', '')}",
    ]
    section_path = md.get("section_path") or []
    if section_path:
        lines.append(f"섹션: {' > '.join(str(part) for part in section_path)}")
    elif md.get("section_title"):
        lines.append(f"섹션: {md['section_title']}")
    if md.get("section_page_start") is not None:
        page = str(md["section_page_start"])
        if md.get("section_page_end") not in (None, md.get("section_page_start")):
            page = f"{page}-{md['section_page_end']}"
        lines.append(f"페이지: {page}")
    header = "\n".join(lines)
    return f"{header}\n{chunk.text}" if chunk.text else header


def chunk_to_document(chunk: Chunk) -> Document:
    metadata = dict(chunk.metadata)
    metadata.update(
        {
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "csv_row_id": chunk.csv_row_id,
        }
    )
    return Document(page_content=embedding_text(chunk), metadata=metadata)


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def _client(qdrant_path: Path | None) -> QdrantClient:
    if qdrant_path is None:
        return QdrantClient(":memory:")
    return QdrantClient(path=str(qdrant_path))


def build_vector_store(
    chunks: list[Chunk],
    embeddings: Embeddings,
    qdrant_path: Path | None,
    lane: str,
) -> QdrantVectorStore:
    """Create a fresh collection and index all chunks. Wipes existing path data."""
    if qdrant_path is not None and qdrant_path.exists():
        shutil.rmtree(qdrant_path)
    client = _client(qdrant_path)
    dim = len(embeddings.embed_query("차원 측정용 텍스트"))
    client.create_collection(
        collection_name=collection_name(lane),
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    store = QdrantVectorStore(
        client=client,
        collection_name=collection_name(lane),
        embedding=embeddings,
    )
    documents = [chunk_to_document(chunk) for chunk in chunks]
    ids = [_point_id(chunk.chunk_id) for chunk in chunks]
    store.add_documents(documents=documents, ids=ids)
    return store


def load_vector_store(
    qdrant_path: Path, embeddings: Embeddings, lane: str
) -> QdrantVectorStore:
    client = _client(qdrant_path)
    return QdrantVectorStore(
        client=client,
        collection_name=collection_name(lane),
        embedding=embeddings,
    )


def _vector_search(
    store: QdrantVectorStore, query: str, top_k: int = 5
) -> list[SearchResult]:
    if top_k <= 0:
        return []
    pairs = store.similarity_search_with_score(query, k=top_k)
    results: list[SearchResult] = []
    for document, score in pairs:
        md = {k: v for k, v in document.metadata.items() if not k.startswith("_")}
        results.append(
            SearchResult(
                chunk_id=md.pop("chunk_id"),
                doc_id=md.pop("doc_id"),
                csv_row_id=md.pop("csv_row_id"),
                score=round(float(score), 8),
                text=document.page_content,
                metadata=md,
            )
        )
    results.sort(key=lambda item: (-item.score, item.doc_id, item.chunk_id))
    return results


@lru_cache(maxsize=8)
def _load_chunk_records_cached(
    index_dir: str, chunks_mtime_ns: int, chunks_size: int
) -> tuple[dict[str, object], ...]:
    del chunks_mtime_ns, chunks_size

    chunks_path = Path(index_dir) / "chunks.jsonl"
    if not chunks_path.exists():
        return ()
    records: list[dict[str, object]] = []
    with chunks_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return tuple(records)


def _load_chunk_records(index_dir: Path) -> tuple[dict[str, object], ...]:
    chunks_path = index_dir / "chunks.jsonl"
    if not chunks_path.exists():
        return ()
    stat = chunks_path.stat()
    return _load_chunk_records_cached(
        str(index_dir.resolve()), stat.st_mtime_ns, stat.st_size
    )


def _section_metadata_candidates(
    index_dir: Path,
    query: str,
    limit: int,
) -> list[SearchResult]:
    if limit <= 0 or "섹션" not in query:
        return []
    candidates: list[SearchResult] = []
    for record in _load_chunk_records(index_dir):
        metadata = dict(record.get("metadata") or {})
        section_title = str(metadata.get("section_title") or "").strip()
        if not section_title or section_title not in query:
            continue
        project_name = str(metadata.get("project_name") or "").strip()
        score = 0.95 if project_name and project_name in query else 0.85
        chunk = Chunk(
            chunk_id=str(record["chunk_id"]),
            doc_id=str(record["doc_id"]),
            csv_row_id=str(record["csv_row_id"]),
            text=str(record.get("text") or ""),
            metadata=metadata,
        )
        candidates.append(
            SearchResult(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                csv_row_id=chunk.csv_row_id,
                score=score,
                text=embedding_text(chunk),
                metadata=metadata,
            )
        )
    candidates.sort(key=lambda item: (-item.score, item.doc_id, item.chunk_id))
    return candidates[:limit]


@lru_cache(maxsize=4)
def _load_bm25_index_cached(
    index_dir: str, chunks_mtime_ns: int, chunks_size: int
) -> BM25Index:
    del chunks_mtime_ns, chunks_size

    return BM25Index.from_index_dir(Path(index_dir))


def _load_bm25_index(index_dir: Path) -> BM25Index:
    chunks_path = index_dir / "chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"chunks file not found: {chunks_path}")
    stat = chunks_path.stat()
    return _load_bm25_index_cached(
        str(index_dir.resolve()), stat.st_mtime_ns, stat.st_size
    )


def _merge_metadata_candidates(
    vector_results: list[SearchResult],
    metadata_results: list[SearchResult],
    top_k: int,
) -> list[SearchResult]:
    by_chunk: dict[str, SearchResult] = {}
    for result in metadata_results + vector_results:
        existing = by_chunk.get(result.chunk_id)
        if existing is None or result.score > existing.score:
            by_chunk[result.chunk_id] = result
    merged = list(by_chunk.values())
    merged.sort(key=lambda item: (-item.score, item.doc_id, item.chunk_id))
    return merged[:top_k]


def search(
    store: QdrantVectorStore,
    query: str,
    top_k: int = 5,
    *,
    retrieval_mode: str = RETRIEVAL_VECTOR,
    index_dir: Path | None = None,
) -> list[SearchResult]:
    if retrieval_mode not in RETRIEVAL_MODES:
        raise ValueError(f"unknown retrieval_mode: {retrieval_mode}")
    if top_k <= 0:
        return []
    if retrieval_mode == RETRIEVAL_VECTOR:
        vector_results = _vector_search(store, query, top_k=top_k)
        if index_dir is None:
            return vector_results
        metadata_results = _section_metadata_candidates(
            index_dir, query, limit=max(top_k * 4, 20)
        )
        if not metadata_results:
            return vector_results
        return _merge_metadata_candidates(vector_results, metadata_results, top_k=top_k)
    if index_dir is None:
        raise ValueError("index_dir is required for hybrid retrieval")

    from .hybrid_retrieval import fuse_ranked_results

    candidate_k = max(top_k * 4, 20)
    vector_results = _vector_search(store, query, top_k=candidate_k)
    bm25_results = _load_bm25_index(index_dir).search(query, top_k=candidate_k)
    if not bm25_results:
        return vector_results[:top_k]
    return fuse_ranked_results(vector_results, bm25_results, top_k=top_k)
