from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .visual_review_batch import DEFAULT_REVIEW_STATUS, run_visual_review_batch


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a reviewer batch for unresolved visual gold records."
    )
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--facts", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--review-status", default=DEFAULT_REVIEW_STATUS)
    parser.add_argument("--max-records", type=int)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    summary = run_visual_review_batch(
        records_path=args.records,
        facts_path=args.facts,
        out_dir=args.out,
        review_status=args.review_status,
        max_records=args.max_records,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
