from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .chunking import Chunk


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
