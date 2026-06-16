from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .visual_gold_eval import run_visual_gold_eval


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate candidate visual facts against reviewer gold facts."
    )
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = run_visual_gold_eval(args.gold, args.candidate, args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
