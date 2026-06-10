from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Any

from .chunking import chunk_documents
from .corpus import inspect_corpus, load_corpus, sha256_file
from .index_store import save_index
from .providers import build_embeddings, embedding_model_name, normalize_lane
from .vector_index import build_vector_store



def _validate_corpus_manifest(manifest: dict[str, Any]) -> None:
    blockers: list[str] = []
    row_count = int(manifest.get("row_count") or 0)
    if not manifest.get("required_columns_present"):
        blockers.append("missing required columns")
    if manifest.get("text_nonempty_count") != row_count:
        blockers.append("empty required text values")
    if manifest.get("normalized_file_matches") != row_count:
        blockers.append("unresolved normalized source files")
    for warning in manifest.get("warnings", []):
        if str(warning).startswith("empty_required_values:"):
            blockers.append("empty required values")
    if blockers:
        raise ValueError(f"corpus inspection failed: {', '.join(blockers)}")

def build_index(
    data_path: Path | str,
    files_path: Path | str,
    out_dir: Path | str,
    chunk_size: int = 500,
    chunk_overlap: int = 80,
    embedding_provider: str = "offline",
) -> dict[str, Any]:
    lane = normalize_lane(embedding_provider)
    data_path = Path(data_path)
    files_path = Path(files_path)
    out_dir = Path(out_dir)
    corpus_manifest = inspect_corpus(data_path, files_path, None)
    _validate_corpus_manifest(corpus_manifest)
    docs = load_corpus(data_path, files_path)
    chunks = chunk_documents(docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    embeddings = build_embeddings(lane)
    build_vector_store(chunks, embeddings, qdrant_path=out_dir / "qdrant", lane=lane)

    manifest: dict[str, Any] = {
        "data_path": str(data_path),
        "files_path": str(files_path),
        "corpus_sha256": sha256_file(data_path),
        "corpus_row_count": corpus_manifest["row_count"],
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "embedding_provider": lane,
        "embedding_model": embedding_model_name(lane),
        "vector_backend": "qdrant_local",
        "chunk_count": len(chunks),
        "unique_docs": len({chunk.doc_id for chunk in chunks}),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_index(out_dir, manifest, chunks)
    return manifest


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Qdrant-backed RFP index.")
    parser.add_argument("--data", required=True, type=Path, help="Path to data_list.csv")
    parser.add_argument("--files", required=True, type=Path, help="Path to source file directory")
    parser.add_argument("--out", required=True, type=Path, help="Index output directory")
    parser.add_argument("--chunk-size", default=500, type=int)
    parser.add_argument("--chunk-overlap", default=80, type=int)
    parser.add_argument(
        "--embedding-provider",
        default="offline",
        help="offline | real_openai (legacy aliases accepted)",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    manifest = build_index(
        data_path=args.data,
        files_path=args.files,
        out_dir=args.out,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        embedding_provider=args.embedding_provider,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
