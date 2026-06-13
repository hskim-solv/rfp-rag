from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .chunking import chunk_documents
from .corpus import CorpusDocument, inspect_corpus, load_corpus, sha256_file
from .index_store import save_index
from .providers import build_embeddings, embedding_model_name, normalize_lane
from .vector_index import build_vector_store


TEXT_SOURCE_PARSED = "parsed"
DEFAULT_PARSE_MANIFEST_PATH = Path("artifacts/parsed_docs/manifest.jsonl")


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


def _read_parse_manifest(path: Path | str) -> dict[str, dict[str, Any]]:
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"parse manifest not found: {manifest_path}")
    rows: dict[str, dict[str, Any]] = {}
    with manifest_path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            doc_id = row.get("doc_id")
            if not doc_id:
                raise ValueError(f"parse manifest row {line_number} missing doc_id")
            rows[str(doc_id)] = row
    return rows


def _read_parsed_text(record: dict[str, Any]) -> str | None:
    if record.get("parse_status") != "parsed":
        return None
    text_path = record.get("text_path")
    if not text_path:
        return None
    path = Path(str(text_path))
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def _parse_lineage_metadata(record: dict[str, Any] | None) -> dict[str, Any]:
    if record is None:
        return {
            "source_parse_status": "missing_parse_record",
            "source_parser_backend": None,
            "source_content_source": None,
            "source_quality": "source_unparsed",
            "source_text_path": None,
            "source_citation_level": None,
            "source_page_citation_available": False,
            "source_page_text_path": None,
            "source_converted_pdf_path": None,
            "source_parse_error_reason": "missing parse manifest row",
        }
    return {
        "source_parse_status": record.get("parse_status"),
        "source_parser_backend": record.get("parser_backend"),
        "source_content_source": record.get("content_source"),
        "source_quality": record.get("source_quality"),
        "source_text_path": record.get("text_path"),
        "source_citation_level": record.get("citation_level"),
        "source_page_citation_available": record.get("page_citation_available") is True,
        "source_page_text_path": record.get("page_text_path"),
        "source_converted_pdf_path": record.get("converted_pdf_path"),
        "source_parse_error_reason": record.get("error_reason"),
    }


def _apply_index_text_source(
    docs: list[CorpusDocument],
    *,
    parse_manifest_path: Path | str | None,
) -> tuple[list[CorpusDocument], dict[str, int]]:
    if parse_manifest_path is None:
        raise ValueError("parse_manifest_path is required")
    parse_rows = _read_parse_manifest(parse_manifest_path)
    source_counts: Counter[str] = Counter()
    resolved_docs: list[CorpusDocument] = []
    for doc in docs:
        record = parse_rows.get(doc.doc_id)
        parsed_text = _read_parsed_text(record) if record is not None else None
        if parsed_text is None:
            reason = (
                "missing parse manifest row"
                if record is None
                else record.get("error_reason") or record.get("parse_status")
            )
            raise ValueError(
                f"parsed source text unavailable for {doc.doc_id}: {reason}"
            )

        source_counts[TEXT_SOURCE_PARSED] += 1
        resolved_docs.append(
            CorpusDocument(
                csv_row_id=doc.csv_row_id,
                doc_id=doc.doc_id,
                text=parsed_text,
                metadata={
                    **doc.metadata,
                    **_parse_lineage_metadata(record),
                    "index_text_source": TEXT_SOURCE_PARSED,
                },
            )
        )
    return resolved_docs, dict(source_counts)


def build_index(
    data_path: Path | str,
    files_path: Path | str,
    out_dir: Path | str,
    chunk_size: int = 500,
    chunk_overlap: int = 80,
    embedding_provider: str = "offline",
    parse_manifest_path: Path | str | None = DEFAULT_PARSE_MANIFEST_PATH,
) -> dict[str, Any]:
    lane = normalize_lane(embedding_provider)
    data_path = Path(data_path)
    files_path = Path(files_path)
    out_dir = Path(out_dir)
    corpus_manifest = inspect_corpus(data_path, files_path, None)
    _validate_corpus_manifest(corpus_manifest)
    docs = load_corpus(data_path, files_path)
    docs, index_text_source_counts = _apply_index_text_source(
        docs,
        parse_manifest_path=parse_manifest_path,
    )
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
        "text_source": TEXT_SOURCE_PARSED,
        "parse_manifest_path": None
        if parse_manifest_path is None
        else str(parse_manifest_path),
        "index_text_source_counts": index_text_source_counts,
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
    parser.add_argument(
        "--data", required=True, type=Path, help="Path to data_list.csv"
    )
    parser.add_argument(
        "--files", required=True, type=Path, help="Path to source file directory"
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="Index output directory"
    )
    parser.add_argument("--chunk-size", default=500, type=int)
    parser.add_argument("--chunk-overlap", default=80, type=int)
    parser.add_argument(
        "--embedding-provider",
        default="offline",
        help="offline | real_openai (legacy aliases accepted)",
    )
    parser.add_argument(
        "--parse-manifest",
        default=DEFAULT_PARSE_MANIFEST_PATH,
        type=Path,
        help="Path to parse_sources manifest.jsonl",
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
        parse_manifest_path=args.parse_manifest,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
