from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rfp_rag.evaluate import reaggregate_metrics
from rfp_rag.judge import JUDGED_QUERY_TYPES, judge_predictions
from rfp_rag.stage2_real import finalize_stage2_real
from rfp_rag.tracing import flush_tracing

JUDGE_METRICS = ("faithfulness", "answer_relevancy")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _needs_judge(row: dict[str, Any]) -> bool:
    if row.get("query_type") not in JUDGED_QUERY_TYPES:
        return False
    judge = row.get("judge") or {}
    if not isinstance(judge, dict):
        return True
    return any(
        not isinstance(judge.get(metric), int | float) for metric in JUDGE_METRICS
    )


def rejudge_missing_stage2(
    *,
    root: Path = Path("."),
    out_dir: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    out_dir = out_dir or root / "artifacts/eval_stage2_real"
    predictions_path = out_dir / "predictions.jsonl"
    predictions = _read_jsonl(predictions_path)
    missing_indexes = [idx for idx, row in enumerate(predictions) if _needs_judge(row)]
    if not missing_indexes:
        metrics = reaggregate_metrics(out_dir, provider="real_openai")
        summary = finalize_stage2_real(root=root, metrics_path=out_dir / "metrics.json")
        return {
            "stage2_rejudge_missing_complete": summary["holdout_quality_complete"],
            "missing_judged_count": 0,
            "metrics": metrics,
            "stage2_summary": summary,
        }

    targets = []
    for idx in missing_indexes:
        row = dict(predictions[idx])
        row.pop("judge", None)
        targets.append(row)
    judged = judge_predictions(targets)
    flush_tracing()
    for idx, row in zip(missing_indexes, judged):
        predictions[idx] = row
    _write_jsonl(predictions_path, predictions)
    metrics = reaggregate_metrics(out_dir, provider="real_openai")
    summary = finalize_stage2_real(root=root, metrics_path=out_dir / "metrics.json")
    return {
        "stage2_rejudge_missing_complete": summary["holdout_quality_complete"],
        "missing_judged_count": len(missing_indexes),
        "metrics": metrics,
        "stage2_summary": summary,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Rejudge only Stage 2 real predictions with missing judge scores, then "
            "reaggregate and finalize the Stage 2 contract."
        )
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    summary = rejudge_missing_stage2(root=args.root, out_dir=args.out_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["stage2_rejudge_missing_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
