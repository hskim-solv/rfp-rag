from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .visual_gold_eval import (
    VISUAL_CANDIDATE_DEFAULT_THRESHOLDS,
    check_visual_candidate_summary,
)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check visual candidate evaluation metrics against thresholds."
    )
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--min-precision",
        default=VISUAL_CANDIDATE_DEFAULT_THRESHOLDS["min_precision"],
        type=float,
    )
    parser.add_argument(
        "--min-recall",
        default=VISUAL_CANDIDATE_DEFAULT_THRESHOLDS["min_recall"],
        type=float,
    )
    parser.add_argument(
        "--min-f1",
        default=VISUAL_CANDIDATE_DEFAULT_THRESHOLDS["min_f1"],
        type=float,
    )
    parser.add_argument(
        "--max-negative-violation-count",
        default=VISUAL_CANDIDATE_DEFAULT_THRESHOLDS["max_negative_violation_count"],
        type=int,
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    result = check_visual_candidate_summary(
        summary,
        min_precision=args.min_precision,
        min_recall=args.min_recall,
        min_f1=args.min_f1,
        max_negative_violation_count=args.max_negative_violation_count,
    )
    if args.out is not None:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "summary.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
