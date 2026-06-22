from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.stage3_agent_scorecard import build_stage3_agent_scorecard, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_complete_inputs(root: Path) -> None:
    _write_json(
        root / "artifacts/eval_agent/metrics.json",
        {
            "agent_lane_complete": True,
            "routing_accuracy": 1.0,
            "tool_accuracy": 1.0,
            "rewrite_recovery": 1.0,
            "loop_termination": 1.0,
        },
    )
    _write_json(
        root / "artifacts/eval_agent_stress/metrics.json",
        {
            "agent_stress_complete": True,
            "metrics": {
                "trajectory_pass_rate": 1.0,
                "branch_coverage": 1.0,
                "thread_id_isolation_pass": 1.0,
                "hitl_approval_convergence": 1.0,
                "no_side_effect_before_approval": 1.0,
                "checkpoint_close_path_pass": 1.0,
                "audit_arg_redaction_pass": 1.0,
                "ops_tool_budget_violation_count": 0,
            },
        },
    )
    _write_json(
        root / "artifacts/agent_orchestration/summary.json",
        {
            "agent_orchestration_upgrade_complete": True,
            "metrics": {
                "planner_executor_or_supervisor_worker_pass": 1.0,
                "multi_tool_plan_pass": 1.0,
                "bounded_retry_reflection_pass": 1.0,
                "human_approval_node_pass": 1.0,
                "state_schema_validation_pass": 1.0,
            },
        },
    )
    _write_jsonl(
        root / "artifacts/eval_agent_stress/replay.jsonl",
        [
            {"id": "direct_rag", "ok": True},
            {"id": "rewrite_recovery", "ok": True},
            {"id": "abstain", "ok": True},
            {"id": "metadata_tool", "ok": True},
            {"id": "hitl_approve", "ok": True},
            {"id": "hitl_reject", "ok": True},
            {"id": "thread_reuse", "ok": True},
        ],
    )
    _write_jsonl(
        root / "artifacts/agent_orchestration/scenarios.jsonl",
        [
            {
                "id": "bid_readiness_plan",
                "requires_human_approval": True,
                "executor_steps": [
                    {"tool": "search_rfp"},
                    {"tool": "aggregate_metadata"},
                    {"tool": "human_approval"},
                ],
            },
            {
                "id": "cross_document_compare_plan",
                "requires_human_approval": False,
                "executor_steps": [
                    {"tool": "search_rfp"},
                    {"tool": "aggregate_metadata"},
                ],
            },
        ],
    )
    _write_jsonl(
        root / "artifacts/eval_agent/agent_artifacts/audit.jsonl",
        [{"tool": "search_rfp"} for _ in range(100)],
    )


def test_build_stage3_agent_scorecard_accepts_complete_evidence(
    tmp_path: Path,
) -> None:
    _write_complete_inputs(tmp_path)

    summary = build_stage3_agent_scorecard(root=tmp_path)

    assert summary["stage3_agent_scorecard_complete"] is True
    assert summary["failed"] == []
    assert summary["metrics"]["required_replay_coverage"] == 1.0
    assert summary["metrics"]["approval_scenario_count"] == 1.0


def test_build_stage3_agent_scorecard_fails_on_missing_replay_id(
    tmp_path: Path,
) -> None:
    _write_complete_inputs(tmp_path)
    _write_jsonl(
        tmp_path / "artifacts/eval_agent_stress/replay.jsonl",
        [{"id": "direct_rag", "ok": True}],
    )

    summary = build_stage3_agent_scorecard(root=tmp_path)

    assert summary["stage3_agent_scorecard_complete"] is False
    assert "required_replay_coverage" in summary["failed"]
    assert "required_replay_ids" in summary["failed"]
    assert "hitl_approve" in summary["missing_replay_ids"]


def test_stage3_agent_scorecard_cli_writes_summary(tmp_path: Path) -> None:
    _write_complete_inputs(tmp_path)
    out = tmp_path / "out/summary.json"

    rc = main(["--root", str(tmp_path), "--out", str(out)])

    assert rc == 0
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["stage3_agent_scorecard_complete"] is True
