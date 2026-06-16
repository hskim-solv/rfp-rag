from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .visual_tesseract_candidate import run_visual_tesseract_candidate


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate local Tesseract OCR visual candidate facts."
    )
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--ocr-text", type=Path, default=None)
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--lang", default="kor+eng")
    parser.add_argument("--psm", type=int, default=11)
    parser.add_argument("--pdftoppm-bin", default="pdftoppm")
    parser.add_argument("--tesseract-bin", default="tesseract")
    parser.add_argument("--timeout-seconds", type=int, default=20)
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
    summary = run_visual_tesseract_candidate(
        args.records,
        args.out,
        ocr_text_path=args.ocr_text,
        dpi=args.dpi,
        lang=args.lang,
        psm=args.psm,
        pdftoppm_bin=args.pdftoppm_bin,
        tesseract_bin=args.tesseract_bin,
        timeout_seconds=args.timeout_seconds,
        review_statuses=args.review_statuses,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
