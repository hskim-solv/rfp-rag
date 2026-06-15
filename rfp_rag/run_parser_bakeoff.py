from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .corpus import load_corpus
from .parser_bakeoff import (
    load_parse_manifest,
    run_backend_for_sample,
    select_bakeoff_samples,
    write_bakeoff_artifacts,
)

DEFAULT_BACKENDS = ["hwp5txt", "hwp5html", "hwp5odt", "rhwp", "unhwp", "hwpxkit", "hwpkit", "libreoffice_pdf"]


def run_parser_bakeoff(
    data_path: Path | str,
    files_path: Path | str,
    parse_manifest_path: Path | str,
    out_dir: Path | str,
    *,
    backends: list[str] | None = None,
    hwp_limit: int = 12,
    include_pdfs: bool = True,
    timeout_seconds: int = 60,
) -> dict[str, object]:
    docs = load_corpus(data_path, files_path)
    manifest_rows = load_parse_manifest(parse_manifest_path)
    samples = select_bakeoff_samples(docs, manifest_rows, hwp_limit=hwp_limit, include_pdfs=include_pdfs)
    selected_backends = backends or DEFAULT_BACKENDS
    results = []
    for sample in samples:
        for backend in selected_backends:
            results.append(
                run_backend_for_sample(
                    sample,
                    backend=backend,
                    out_dir=out_dir,
                    timeout_seconds=timeout_seconds,
                )
            )
    return write_bakeoff_artifacts(samples, results, out_dir)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run parser/render bakeoff on representative RFP source files.")
    parser.add_argument("--data", required=True, type=Path, help="Path to data_list.csv")
    parser.add_argument("--files", required=True, type=Path, help="Path to source file directory")
    parser.add_argument("--parse-manifest", required=True, type=Path, help="Path to artifacts/parsed_docs/manifest.jsonl")
    parser.add_argument("--out", required=True, type=Path, help="Bakeoff artifact output directory")
    parser.add_argument("--backend", action="append", dest="backends", help="Backend to run; repeat for multiple backends")
    parser.add_argument("--hwp-limit", default=12, type=int, help="Number of HWP samples")
    parser.add_argument("--timeout-seconds", default=60, type=int, help="Per backend/sample timeout")
    parser.add_argument("--no-pdfs", action="store_true", help="Exclude PDF reference samples")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    summary = run_parser_bakeoff(
        args.data,
        args.files,
        args.parse_manifest,
        args.out,
        backends=args.backends,
        hwp_limit=args.hwp_limit,
        include_pdfs=not args.no_pdfs,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
