from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_OUT = Path("artifacts/paid_lane_plan/summary.json")
REQUIRED_ENV_VARS = ["OPENAI_API_KEY"]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _cost_budget(root: Path) -> dict[str, Any]:
    budget = _read_json(root / "artifacts/cost_budget/summary.json")
    return {
        "cost_budget_complete": budget.get("cost_budget_complete"),
        "max_estimated_cost_usd": budget.get("max_estimated_cost_usd"),
        "total_estimated_cost_usd": budget.get("total_estimated_cost_usd"),
    }


def _step(
    step_id: str,
    command: str,
    *,
    writes: list[str] | None = None,
    reads: list[str] | None = None,
    cost_bearing: bool = False,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "command": command,
        "reads": reads or [],
        "writes": writes or [],
        "cost_bearing": cost_bearing,
    }


def _planned_steps() -> list[dict[str, Any]]:
    return [
        _step(
            "real_index_v6",
            "uv run python -m rfp_rag.build_index "
            "--data data/data_list.csv --files data/files "
            "--out artifacts/index_real --chunk-size 500 --chunk-overlap 80 "
            "--embedding-provider openai "
            "--parse-manifest artifacts/parsed_docs/manifest.jsonl",
            reads=[
                "data/data_list.csv",
                "data/files",
                "artifacts/parsed_docs/manifest.jsonl",
            ],
            writes=["artifacts/index_real"],
            cost_bearing=True,
        ),
        _step(
            "real_eval_v6",
            "uv run python -m rfp_rag.evaluate "
            "--data data/data_list.csv --index artifacts/index_real "
            "--out artifacts/eval_real --provider real_openai --top-k 5 "
            "--min-score 0.47 "
            "--visual-records artifacts/visual_structure_reviewed/records.jsonl",
            reads=[
                "artifacts/index_real",
                "artifacts/visual_structure_reviewed/records.jsonl",
            ],
            writes=["artifacts/eval_real"],
            cost_bearing=True,
        ),
        _step(
            "stage2_real_eval",
            "uv run python -m rfp_rag.evaluate "
            "--data data/data_list.csv --index artifacts/index_real "
            "--out artifacts/eval_stage2_real --provider real_openai --top-k 5 "
            "--min-score 0.47 "
            "--visual-records artifacts/visual_structure_stage2_reviewed/records.jsonl",
            reads=[
                "artifacts/index_real",
                "artifacts/visual_structure_stage2_reviewed/records.jsonl",
            ],
            writes=["artifacts/eval_stage2_real"],
            cost_bearing=True,
        ),
        _step(
            "stage2_real_finalize",
            "uv run python -m rfp_rag.stage2_real",
            reads=[
                "artifacts/eval_stage2_real/metrics.json",
                "artifacts/eval_stage2/coverage.json",
            ],
            writes=["artifacts/eval_stage2_real/metrics.json"],
        ),
        _step(
            "same_set_open_reranker_eval",
            "uv run python -m rfp_rag.evaluate "
            "--data data/data_list.csv --index artifacts/index_open "
            "--out artifacts/eval_open_rerank --provider open --top-k 5 "
            "--min-score 0.55 --reranker llm --rerank-candidate-k 10 "
            "--visual-records artifacts/visual_structure_reviewed/records.jsonl",
            reads=[
                "artifacts/index_open",
                "artifacts/visual_structure_reviewed/records.jsonl",
            ],
            writes=["artifacts/eval_open_rerank"],
            cost_bearing=True,
        ),
        _step(
            "retrieval_bakeoff",
            "uv run python -m rfp_rag.retrieval_bakeoff",
            reads=[
                "artifacts/eval/metrics.json",
                "artifacts/eval_bm25_offline/metrics.json",
                "artifacts/eval_hybrid_offline/metrics.json",
                "artifacts/eval_open_rerank/metrics.json",
            ],
            writes=["artifacts/retrieval_bakeoff/summary.json"],
        ),
        _step(
            "cost_budget",
            "uv run python -m rfp_rag.cost_budget",
            reads=[
                "artifacts/eval_open",
                "artifacts/eval_real",
                "artifacts/eval_open_rerank",
                "artifacts/eval_stage2_real",
            ],
            writes=["artifacts/cost_budget/summary.json"],
        ),
        _step(
            "gate_status",
            "uv run python -m rfp_rag.gate_status",
            reads=["artifacts/eval_real", "artifacts/eval_agent", "artifacts/eval"],
        ),
        _step(
            "portfolio_check",
            "uv run python -m rfp_rag.portfolio_check "
            "--out artifacts/portfolio_readiness.json",
            reads=["artifacts"],
            writes=["artifacts/portfolio_readiness.json"],
        ),
    ]


def build_paid_lane_plan(
    *,
    root: Path = Path("."),
    out: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    out = out or root / DEFAULT_OUT
    steps = _planned_steps()
    summary = {
        "paid_lane_plan_complete": True,
        "approval_required": True,
        "does_not_execute_paid_lanes": True,
        "required_env_vars": REQUIRED_ENV_VARS,
        "current_cost_budget": _cost_budget(root),
        "steps": steps,
        "cost_bearing_step_ids": [
            step["id"] for step in steps if step.get("cost_bearing") is True
        ],
        "post_run_success_commands": [
            "uv run python -m rfp_rag.gate_status",
            "uv run python -m rfp_rag.portfolio_check --out artifacts/portfolio_readiness.json",
        ],
        "stop_condition": (
            "Do not execute cost-bearing steps until the user explicitly approves "
            "paid/API execution for this plan."
        ),
    }
    _write_json(out, summary)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write the explicit paid/API lane execution plan without running it."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    summary = build_paid_lane_plan(root=args.root, out=args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["paid_lane_plan_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
