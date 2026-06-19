from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.paid_lane_plan import build_paid_lane_plan, main


def _step(summary: dict, step_id: str) -> dict:
    return next(step for step in summary["steps"] if step["id"] == step_id)


def test_build_paid_lane_plan_records_required_approval_and_artifacts(
    tmp_path: Path,
) -> None:
    summary = build_paid_lane_plan(root=tmp_path)

    assert summary["paid_lane_plan_complete"] is True
    assert summary["approval_required"] is True
    assert summary["does_not_execute_paid_lanes"] is True
    assert summary["required_env_vars"] == ["OPENAI_API_KEY"]
    assert [step["id"] for step in summary["steps"]] == [
        "real_index_v6",
        "real_eval_v6",
        "stage2_real_eval",
        "stage2_real_finalize",
        "stage3_holdout_case_freeze",
        "stage3_real_eval",
        "stage3_holdout_finalize",
        "same_set_open_reranker_eval",
        "retrieval_bakeoff",
        "cost_budget",
        "gate_status",
        "portfolio_check",
    ]
    assert _step(summary, "real_eval_v6")["writes"] == ["artifacts/eval_real"]
    assert "--out artifacts/eval_real" in _step(summary, "real_eval_v6")["command"]
    assert "--provider real_openai" in _step(summary, "real_eval_v6")["command"]
    assert _step(summary, "stage2_real_eval")["writes"] == [
        "artifacts/eval_stage2_real"
    ]
    assert (
        "--visual-records artifacts/visual_structure_stage2_reviewed/records.jsonl"
        in _step(summary, "stage2_real_eval")["command"]
    )
    assert _step(summary, "stage2_real_finalize")["command"] == (
        "uv run python -m rfp_rag.stage2_real"
    )
    assert (
        "eval_sets/stage3_holdout/cases.jsonl"
        in _step(summary, "stage3_holdout_case_freeze")["reads"]
    )
    assert _step(summary, "stage3_real_eval")["cost_bearing"] is True
    assert _step(summary, "stage3_real_eval")["writes"] == [
        "artifacts/eval_stage3_raw/metrics.json"
    ]
    assert (
        "--raw-metrics artifacts/eval_stage3_raw/metrics.json"
        in _step(summary, "stage3_holdout_finalize")["command"]
    )
    assert _step(summary, "same_set_open_reranker_eval")["writes"] == [
        "artifacts/eval_open_rerank"
    ]
    assert "--reranker llm" in _step(summary, "same_set_open_reranker_eval")["command"]
    assert (
        "--out artifacts/eval_open_rerank"
        in _step(summary, "same_set_open_reranker_eval")["command"]
    )


def test_build_paid_lane_plan_includes_current_cost_budget_when_present(
    tmp_path: Path,
) -> None:
    budget_path = tmp_path / "artifacts/cost_budget/summary.json"
    budget_path.parent.mkdir(parents=True)
    budget_path.write_text(
        json.dumps(
            {
                "cost_budget_complete": True,
                "total_estimated_cost_usd": 2.5,
                "max_estimated_cost_usd": 5.0,
            }
        ),
        encoding="utf-8",
    )

    summary = build_paid_lane_plan(root=tmp_path)

    assert summary["current_cost_budget"] == {
        "cost_budget_complete": True,
        "max_estimated_cost_usd": 5.0,
        "total_estimated_cost_usd": 2.5,
    }


def test_paid_lane_plan_cli_writes_summary(tmp_path: Path) -> None:
    rc = main(["--root", str(tmp_path)])

    assert rc == 0
    saved = json.loads(
        (tmp_path / "artifacts/paid_lane_plan/summary.json").read_text(encoding="utf-8")
    )
    assert saved["paid_lane_plan_complete"] is True
