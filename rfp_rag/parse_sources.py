from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .corpus import load_corpus
from .source_parsing import (
    build_parse_record,
    parse_document_source,
    write_parse_artifacts,
)


def parse_sources(
    data_path: Path | str,
    files_path: Path | str,
    out_dir: Path | str,
    *,
    timeout_seconds: int = 60,
    enable_page_citation: bool = True,
) -> dict[str, object]:
    docs = load_corpus(data_path, files_path)
    out_dir = Path(out_dir)
    records = []
    for doc in docs:
        result = parse_document_source(
            doc, timeout_seconds=timeout_seconds, out_dir=out_dir
        )
        records.append(
            build_parse_record(
                doc,
                result,
                out_dir,
                enable_page_citation=enable_page_citation,
                citation_timeout_seconds=timeout_seconds,
            )
        )
    return write_parse_artifacts(records, out_dir)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse original RFP source files into local text artifacts."
    )
    parser.add_argument(
        "--data", required=True, type=Path, help="Path to data_list.csv"
    )
    parser.add_argument(
        "--files", required=True, type=Path, help="Path to source file directory"
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="Parsed artifact output directory"
    )
    parser.add_argument(
        "--timeout-seconds", default=60, type=int, help="Per-document parser timeout"
    )
    parser.add_argument(
        "--no-page-citation",
        action="store_true",
        help="Skip HWP/PDF page-citation evidence generation",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    summary = parse_sources(
        args.data,
        args.files,
        args.out,
        timeout_seconds=args.timeout_seconds,
        enable_page_citation=not args.no_page_citation,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
