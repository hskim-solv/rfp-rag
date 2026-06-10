from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .corpus import CorpusDocument

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+|[^\s]")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    csv_row_id: str
    text: str
    metadata: dict[str, Any]


def token_spans(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0), m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]


def _window_text(text: str, spans: list[tuple[str, int, int]], start: int, end: int) -> str:
    if not spans:
        return text.strip()
    char_start = spans[start][1]
    char_end = spans[end - 1][2]
    return text[char_start:char_end].strip()


def chunk_document(doc: CorpusDocument, chunk_size: int = 500, chunk_overlap: int = 80) -> list[Chunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be non-negative")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    text = (doc.text or "").strip()
    spans = token_spans(text)
    if not text:
        windows = [(0, 0, "")]
    elif len(spans) <= chunk_size:
        windows = [(0, len(spans), text)]
    else:
        windows = []
        step = chunk_size - chunk_overlap
        start = 0
        while start < len(spans):
            end = min(start + chunk_size, len(spans))
            windows.append((start, end, _window_text(text, spans, start, end)))
            if end >= len(spans):
                break
            start += step

    chunks: list[Chunk] = []
    for idx, (start, end, chunk_text) in enumerate(windows):
        metadata = dict(doc.metadata)
        metadata.update(
            {
                "chunk_index": idx,
                "chunk_token_start": start,
                "chunk_token_end": end,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
            }
        )
        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}:chunk:{idx}",
                doc_id=doc.doc_id,
                csv_row_id=doc.csv_row_id,
                text=chunk_text,
                metadata=metadata,
            )
        )
    return chunks


def chunk_documents(docs: list[CorpusDocument], chunk_size: int = 500, chunk_overlap: int = 80) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in docs:
        chunks.extend(chunk_document(doc, chunk_size=chunk_size, chunk_overlap=chunk_overlap))
    return chunks
