from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .visual_local_baseline import run_visual_local_baseline


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate deterministic local visual candidate facts."
    )
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--review-status",
        action="append",
        dest="review_statuses",
        help="Review status to include. Repeat to include multiple statuses.",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    summary = run_visual_local_baseline(
        args.records,
        args.out,
        review_statuses=args.review_statuses,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
