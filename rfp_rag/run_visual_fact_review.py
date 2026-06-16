from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .visual_facts import run_visual_fact_review


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Merge reviewer visual facts into visual-structure records."
    )
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--facts", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    summary = run_visual_fact_review(
        records_path=args.records,
        facts_path=args.facts,
        out_dir=args.out,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
