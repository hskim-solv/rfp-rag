from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .rag_chain import DEFAULT_MIN_SCORE, answer_query


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Answer a Korean RFP question from a local index with citations.")
    parser.add_argument("--index", required=True, type=Path, help="Index directory")
    parser.add_argument("--query", required=True, help="Question to answer")
    parser.add_argument("--top-k", default=5, type=int)
    parser.add_argument("--min-score", default=DEFAULT_MIN_SCORE, type=float)
    parser.add_argument("--provider", default=None, help="offline | real_openai (default: index lane)")
    parser.add_argument("--out", type=Path, help="Optional JSON output path")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    response = answer_query(
        args.index, args.query, top_k=args.top_k, min_score=args.min_score, provider=args.provider
    )
    payload = json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
