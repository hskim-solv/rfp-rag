from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.agent_stress import evaluate_agent_stress, main


def test_evaluate_agent_stress_writes_stage2_contract_artifact(tmp_path: Path) -> None:
    summary = evaluate_agent_stress(root=tmp_path)

    assert summary["agent_stress_complete"] is True
    assert len(summary["scenario_matrix_hash"]) == 64
    assert (
        summary["branch_replay_artifact_path"]
        == "artifacts/eval_agent_stress/replay.jsonl"
    )
    assert summary["metrics"] == {
        "branch_coverage": 1.0,
        "checkpoint_close_path_pass": 1.0,
        "hitl_approval_convergence": 1.0,
        "no_side_effect_before_approval": 1.0,
        "audit_arg_redaction_pass": 1.0,
        "thread_id_isolation_pass": 1.0,
        "ops_tool_budget_violation_count": 0,
        "trajectory_pass_rate": 1.0,
    }
    assert summary["failed"] == []
    assert (tmp_path / "artifacts/eval_agent_stress/metrics.json").is_file()
    replay = (tmp_path / "artifacts/eval_agent_stress/replay.jsonl").read_text(
        encoding="utf-8"
    )
    assert "hitl_approve" in replay
    assert "hitl_reject" in replay


def test_agent_stress_cli_writes_summary(tmp_path: Path) -> None:
    rc = main(["--root", str(tmp_path)])

    assert rc == 0
    saved = json.loads(
        (tmp_path / "artifacts/eval_agent_stress/metrics.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved["agent_stress_complete"] is True
