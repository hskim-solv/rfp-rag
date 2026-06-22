from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_OUT = Path("artifacts/stage3_agent_scorecard/summary.json")

REQUIRED_REPLAY_IDS = {
    "direct_rag",
    "rewrite_recovery",
    "abstain",
    "metadata_tool",
    "hitl_approve",
    "hitl_reject",
    "thread_reuse",
}

THRESHOLDS = {
    "agent_lane_complete": 1.0,
    "routing_accuracy": 0.90,
    "tool_accuracy": 0.90,
    "rewrite_recovery": 0.80,
    "loop_termination": 1.0,
    "trajectory_pass_rate": 1.0,
    "branch_coverage": 1.0,
    "thread_id_isolation_pass": 1.0,
    "hitl_approval_convergence": 1.0,
    "no_side_effect_before_approval": 1.0,
    "checkpoint_close_path_pass": 1.0,
    "audit_arg_redaction_pass": 1.0,
    "ops_tool_budget_violation_count": 0,
    "planner_executor_or_supervisor_worker_pass": 1.0,
    "multi_tool_plan_pass": 1.0,
    "bounded_retry_reflection_pass": 1.0,
    "human_approval_node_pass": 1.0,
    "state_schema_validation_pass": 1.0,
    "required_replay_coverage": 1.0,
    "scenario_plan_count": 2,
    "approval_scenario_count": 1,
    "audit_line_count": 100,
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _float(value: Any, default: float = 0.0) -> float:
    return float(value) if isinstance(value, int | float | bool) else default


def _replay_coverage(rows: list[dict[str, Any]]) -> tuple[float, list[str]]:
    ok_ids = {str(row.get("id")) for row in rows if row.get("ok") is True}
    missing = sorted(REQUIRED_REPLAY_IDS - ok_ids)
    return (1.0 if not missing else 0.0), missing


def _scenario_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    approval_count = sum(
        1 for row in rows if row.get("requires_human_approval") is True
    )
    multi_tool_count = 0
    for row in rows:
        tools = {
            str(step.get("tool"))
            for step in row.get("executor_steps") or []
            if isinstance(step, dict)
        }
        if {"search_rfp", "aggregate_metadata"} <= tools:
            multi_tool_count += 1
    return {
        "scenario_plan_count": float(len(rows)),
        "approval_scenario_count": float(approval_count),
        "multi_tool_scenario_count": float(multi_tool_count),
    }


def _evaluate_thresholds(metrics: dict[str, float]) -> list[str]:
    failed: list[str] = []
    for key, threshold in THRESHOLDS.items():
        value = metrics.get(key)
        if value is None:
            failed.append(key)
            continue
        if key == "ops_tool_budget_violation_count":
            if value != threshold:
                failed.append(key)
        elif value < threshold:
            failed.append(key)
    return failed


def build_stage3_agent_scorecard(*, root: Path = Path(".")) -> dict[str, Any]:
    root = root.resolve()
    paths = {
        "agent_lane": root / "artifacts/eval_agent/metrics.json",
        "agent_stress": root / "artifacts/eval_agent_stress/metrics.json",
        "agent_replay": root / "artifacts/eval_agent_stress/replay.jsonl",
        "agent_orchestration": root / "artifacts/agent_orchestration/summary.json",
        "agent_scenarios": root / "artifacts/agent_orchestration/scenarios.jsonl",
        "agent_audit": root / "artifacts/eval_agent/agent_artifacts/audit.jsonl",
    }
    missing = [
        name
        for name, path in paths.items()
        if not path.exists() or (path.is_file() and path.stat().st_size == 0)
    ]

    agent_lane = _read_json(paths["agent_lane"])
    stress = _read_json(paths["agent_stress"])
    orchestration = _read_json(paths["agent_orchestration"])
    stress_metrics = stress.get("metrics") or {}
    orchestration_metrics = orchestration.get("metrics") or {}
    replay_rows = _read_jsonl(paths["agent_replay"])
    scenario_rows = _read_jsonl(paths["agent_scenarios"])
    audit_rows = _read_jsonl(paths["agent_audit"])
    replay_coverage, missing_replay_ids = _replay_coverage(replay_rows)
    scenario_metrics = _scenario_metrics(scenario_rows)

    metrics = {
        "agent_lane_complete": 1.0 if agent_lane.get("agent_lane_complete") else 0.0,
        "routing_accuracy": _float(agent_lane.get("routing_accuracy")),
        "tool_accuracy": _float(agent_lane.get("tool_accuracy")),
        "rewrite_recovery": _float(agent_lane.get("rewrite_recovery")),
        "loop_termination": _float(agent_lane.get("loop_termination")),
        "trajectory_pass_rate": _float(stress_metrics.get("trajectory_pass_rate")),
        "branch_coverage": _float(stress_metrics.get("branch_coverage")),
        "thread_id_isolation_pass": _float(
            stress_metrics.get("thread_id_isolation_pass")
        ),
        "hitl_approval_convergence": _float(
            stress_metrics.get("hitl_approval_convergence")
        ),
        "no_side_effect_before_approval": _float(
            stress_metrics.get("no_side_effect_before_approval")
        ),
        "checkpoint_close_path_pass": _float(
            stress_metrics.get("checkpoint_close_path_pass")
        ),
        "audit_arg_redaction_pass": _float(
            stress_metrics.get("audit_arg_redaction_pass")
        ),
        "ops_tool_budget_violation_count": _float(
            stress_metrics.get("ops_tool_budget_violation_count")
        ),
        "planner_executor_or_supervisor_worker_pass": _float(
            orchestration_metrics.get("planner_executor_or_supervisor_worker_pass")
        ),
        "multi_tool_plan_pass": _float(
            orchestration_metrics.get("multi_tool_plan_pass")
        ),
        "bounded_retry_reflection_pass": _float(
            orchestration_metrics.get("bounded_retry_reflection_pass")
        ),
        "human_approval_node_pass": _float(
            orchestration_metrics.get("human_approval_node_pass")
        ),
        "state_schema_validation_pass": _float(
            orchestration_metrics.get("state_schema_validation_pass")
        ),
        "required_replay_coverage": replay_coverage,
        "audit_line_count": float(len(audit_rows)),
        **scenario_metrics,
    }

    failed = [f"missing:{name}" for name in missing]
    failed.extend(_evaluate_thresholds(metrics))
    if not stress.get("agent_stress_complete"):
        failed.append("agent_stress_complete")
    if not orchestration.get("agent_orchestration_upgrade_complete"):
        failed.append("agent_orchestration_upgrade_complete")
    if missing_replay_ids:
        failed.append("required_replay_ids")

    return {
        "stage3_agent_scorecard_complete": not failed,
        "metrics": metrics,
        "thresholds": THRESHOLDS,
        "failed": sorted(set(failed)),
        "missing_replay_ids": missing_replay_ids,
        "required_replay_ids": sorted(REQUIRED_REPLAY_IDS),
        "evidence_paths": {
            key: str(path.relative_to(root)) for key, path in paths.items()
        },
        "method": {
            "required_replay_coverage": (
                "all deterministic replay rows for direct RAG, rewrite recovery, "
                "abstention, metadata tool route, HITL approve/reject, and thread "
                "reuse must be present and ok=true"
            ),
            "planner_executor_or_supervisor_worker_pass": (
                "scenario replay evidence over the existing typed LangGraph workflow; "
                "does not claim a dynamic planner runtime"
            ),
        },
        "notes": [
            "This scorecard is deterministic and credential-free.",
            "It aggregates existing LangGraph lane, stress replay, orchestration, scenario, and audit evidence.",
            "Planner-executor is claimed as scenario evidence over the current graph, not a dynamic planner node.",
        ],
    }


def write_stage3_agent_scorecard(
    *, root: Path = Path("."), out: Path | None = None
) -> dict[str, Any]:
    root = root.resolve()
    summary = build_stage3_agent_scorecard(root=root)
    out = out or root / DEFAULT_OUT
    _write_json(out, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate Stage 3 agent workflow evidence into a senior portfolio scorecard."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    summary = write_stage3_agent_scorecard(root=args.root, out=args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["stage3_agent_scorecard_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
