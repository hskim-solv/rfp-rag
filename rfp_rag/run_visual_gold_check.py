from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .visual_facts import (
    VISUAL_GOLD_DEFAULT_THRESHOLDS,
    check_visual_gold_summary,
)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check reviewer visual-fact gold-set coverage."
    )
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument(
        "--min-accepted-record-ratio",
        default=VISUAL_GOLD_DEFAULT_THRESHOLDS["min_accepted_record_ratio"],
        type=float,
    )
    parser.add_argument(
        "--min-accepted-fact-count",
        default=VISUAL_GOLD_DEFAULT_THRESHOLDS["min_accepted_fact_count"],
        type=int,
    )
    parser.add_argument(
        "--max-needs-review-fact-count",
        default=VISUAL_GOLD_DEFAULT_THRESHOLDS["max_needs_review_fact_count"],
        type=int,
    )
    parser.add_argument(
        "--max-unknown-record-count",
        default=VISUAL_GOLD_DEFAULT_THRESHOLDS["max_unknown_record_count"],
        type=int,
    )
    parser.add_argument(
        "--max-unsupported-claim-count",
        default=VISUAL_GOLD_DEFAULT_THRESHOLDS["max_unsupported_claim_count"],
        type=int,
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    result = check_visual_gold_summary(
        summary,
        min_accepted_record_ratio=args.min_accepted_record_ratio,
        min_accepted_fact_count=args.min_accepted_fact_count,
        max_needs_review_fact_count=args.max_needs_review_fact_count,
        max_unknown_record_count=args.max_unknown_record_count,
        max_unsupported_claim_count=args.max_unsupported_claim_count,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
