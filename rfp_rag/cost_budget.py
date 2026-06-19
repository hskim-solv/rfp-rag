from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rfp_rag.ops_metrics import summarize_eval_artifacts


DEFAULT_INPUT_COST_PER_1K = 0.005
DEFAULT_OUTPUT_COST_PER_1K = 0.015
DEFAULT_MAX_ESTIMATED_COST_USD = 5.0
EVAL_DIRS = {
    "eval_real": Path("artifacts/eval_real"),
    "eval_open": Path("artifacts/eval_open"),
    "eval_open_rerank": Path("artifacts/eval_open_rerank"),
    "eval_real_rerank": Path("artifacts/eval_real_rerank"),
    "eval_stage2_real": Path("artifacts/eval_stage2_real"),
}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _prediction_count(eval_dir: Path) -> int:
    path = eval_dir / "predictions.jsonl"
    if not path.exists():
        return 0
    return sum(
        1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )


def evaluate_cost_budget(
    *,
    root: Path = Path("."),
    out: Path | None = None,
    max_estimated_cost_usd: float = DEFAULT_MAX_ESTIMATED_COST_USD,
    input_cost_per_1k: float = DEFAULT_INPUT_COST_PER_1K,
    output_cost_per_1k: float = DEFAULT_OUTPUT_COST_PER_1K,
) -> dict[str, Any]:
    root = root.resolve()
    out = out or root / "artifacts/cost_budget/summary.json"
    eval_dirs = {name: root / rel for name, rel in EVAL_DIRS.items()}
    summaries = {
        name: summarize_eval_artifacts(
            eval_dir,
            input_cost_per_1k=input_cost_per_1k,
            output_cost_per_1k=output_cost_per_1k,
        )
        for name, eval_dir in eval_dirs.items()
    }
    prediction_counts = {
        name: _prediction_count(eval_dir) for name, eval_dir in eval_dirs.items()
    }
    total_predictions = sum(prediction_counts.values())
    total_tokens = sum(
        summary["estimated_total_tokens"] for summary in summaries.values()
    )
    total_cost = round(
        sum(summary["estimated_cost_usd"] for summary in summaries.values()), 6
    )
    real_summary = summaries["eval_real"]
    reranker_cost = round(
        summaries["eval_open_rerank"]["estimated_cost_usd"]
        + summaries["eval_real_rerank"]["estimated_cost_usd"],
        6,
    )

    token_record_coverage = 1.0 if total_predictions > 0 and total_tokens > 0 else 0.0
    cost_record_coverage = 1.0 if total_predictions > 0 and total_cost >= 0 else 0.0
    budget_violation_count = 0 if total_cost <= max_estimated_cost_usd else 1
    metrics = {
        "token_record_coverage": token_record_coverage,
        "cost_record_coverage": cost_record_coverage,
        "budget_violation_count": budget_violation_count,
    }
    thresholds = {
        "token_record_coverage": 1.0,
        "cost_record_coverage": 1.0,
        "budget_violation_count": 0,
    }
    failed = [key for key, threshold in thresholds.items() if metrics[key] != threshold]
    if prediction_counts["eval_real"] == 0:
        failed.append("real_open_run_cost_estimate_usd")
    summary = {
        "cost_budget_complete": not failed,
        "real_open_run_cost_estimate_usd": real_summary["estimated_cost_usd"],
        "open_run_cost_estimate_usd": summaries["eval_open"]["estimated_cost_usd"],
        "reranker_run_cost_estimate_usd": reranker_cost,
        "stage2_real_run_cost_estimate_usd": summaries["eval_stage2_real"][
            "estimated_cost_usd"
        ],
        "total_estimated_cost_usd": total_cost,
        "max_estimated_cost_usd": max_estimated_cost_usd,
        "regression_threshold_rationale": (
            "Deterministic estimate from persisted real/open prediction text; "
            "actual provider billing remains external."
        ),
        "pricing_assumption": {
            "input_cost_per_1k": input_cost_per_1k,
            "output_cost_per_1k": output_cost_per_1k,
        },
        "prediction_counts": dict(sorted(prediction_counts.items())),
        "measured_eval_dirs": [
            str(EVAL_DIRS[name])
            for name, count in sorted(prediction_counts.items())
            if count > 0
        ],
        "metrics": metrics,
        "thresholds": thresholds,
        "failed": sorted(set(failed)),
    }
    _write_json(out, summary)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write Stage 2 cost-budget estimate artifacts."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--max-estimated-cost-usd",
        type=float,
        default=DEFAULT_MAX_ESTIMATED_COST_USD,
    )
    parser.add_argument(
        "--input-cost-per-1k", type=float, default=DEFAULT_INPUT_COST_PER_1K
    )
    parser.add_argument(
        "--output-cost-per-1k", type=float, default=DEFAULT_OUTPUT_COST_PER_1K
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    summary = evaluate_cost_budget(
        root=args.root,
        out=args.out,
        max_estimated_cost_usd=args.max_estimated_cost_usd,
        input_cost_per_1k=args.input_cost_per_1k,
        output_cost_per_1k=args.output_cost_per_1k,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["cost_budget_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
