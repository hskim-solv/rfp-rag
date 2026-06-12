from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from .chunking import Chunk
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
    header = f"사업명: {md.get('project_name', '')}\n발주기관: {md.get('issuer', '')}"
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


def load_vector_store(qdrant_path: Path, embeddings: Embeddings, lane: str) -> QdrantVectorStore:
    client = _client(qdrant_path)
    return QdrantVectorStore(
        client=client,
        collection_name=collection_name(lane),
        embedding=embeddings,
    )


def _vector_search(store: QdrantVectorStore, query: str, top_k: int = 5) -> list[SearchResult]:
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
        return _vector_search(store, query, top_k=top_k)
    if index_dir is None:
        raise ValueError("index_dir is required for hybrid retrieval")

    from .hybrid_retrieval import BM25Index, fuse_ranked_results

    candidate_k = max(top_k * 4, 20)
    vector_results = _vector_search(store, query, top_k=candidate_k)
    bm25_results = BM25Index.from_index_dir(index_dir).search(query, top_k=candidate_k)
    if not bm25_results:
        return vector_results[:top_k]
    return fuse_ranked_results(vector_results, bm25_results, top_k=top_k)
