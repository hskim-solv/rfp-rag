from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.agent_orchestration import evaluate_agent_orchestration, main


def _write_agent_stress(root: Path, *, hitl: float = 1.0) -> None:
    path = root / "artifacts/eval_agent_stress/metrics.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "metrics": {
                    "trajectory_pass_rate": 1.0,
                    "hitl_approval_convergence": hitl,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_evaluate_agent_orchestration_writes_planner_executor_evidence(
    tmp_path: Path,
) -> None:
    _write_agent_stress(tmp_path)

    summary = evaluate_agent_orchestration(root=tmp_path)

    assert summary["agent_orchestration_upgrade_complete"] is True
    assert (
        summary["architecture_pattern"]
        == "typed LangGraph workflow with planner-executor scenario replay evidence"
    )
    assert (
        summary["runtime_non_claim"]
        == "does_not_claim_dynamic_planner_node_or_supervisor_worker_runtime"
    )
    assert summary["metrics"]["planner_executor_or_supervisor_worker_pass"] == 1.0
    assert summary["metrics"]["multi_tool_plan_pass"] == 1.0
    assert summary["metrics"]["human_approval_node_pass"] == 1.0
    scenarios = (tmp_path / "artifacts/agent_orchestration/scenarios.jsonl").read_text(
        encoding="utf-8"
    )
    assert "aggregate_metadata" in scenarios
    assert "human_approval" in scenarios


def test_evaluate_agent_orchestration_fails_closed_without_hitl_evidence(
    tmp_path: Path,
) -> None:
    _write_agent_stress(tmp_path, hitl=0.0)

    summary = evaluate_agent_orchestration(root=tmp_path)

    assert summary["agent_orchestration_upgrade_complete"] is False
    assert "human_approval_node_pass" in summary["failed"]


def test_agent_orchestration_cli_returns_nonzero_on_missing_stress(
    tmp_path: Path,
) -> None:
    rc = main(["--root", str(tmp_path)])

    assert rc == 1
