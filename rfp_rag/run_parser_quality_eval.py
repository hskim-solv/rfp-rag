from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .parser_quality_eval import evaluate_parser_quality, write_quality_artifacts


def run_parser_quality_eval(
    parsed_dir: Path | str,
    out_dir: Path | str,
    *,
    quality_threshold: float = 0.6,
) -> dict[str, object]:
    quality_records, summary = evaluate_parser_quality(
        parsed_dir,
        quality_threshold=quality_threshold,
    )
    return write_quality_artifacts(quality_records, summary, out_dir)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate parsed RFP source quality against page evidence artifacts."
    )
    parser.add_argument(
        "--parsed-dir", required=True, type=Path, help="Path to artifacts/parsed_docs"
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="Parser quality output directory"
    )
    parser.add_argument(
        "--quality-threshold",
        default=0.6,
        type=float,
        help="Risk threshold for low-quality docs",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    summary = run_parser_quality_eval(
        args.parsed_dir,
        args.out,
        quality_threshold=args.quality_threshold,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
