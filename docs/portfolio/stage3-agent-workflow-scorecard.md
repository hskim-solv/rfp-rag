# Stage 3 Agent Workflow Scorecard

Date: 2026-06-22

This document explains the deterministic Stage 3 agent workflow scorecard used
by the senior portfolio roadmap. The machine-readable artifact is generated
with:

```bash
uv run python -m rfp_rag.stage3_agent_scorecard
```

Output:

- `artifacts/stage3_agent_scorecard/summary.json`

## Purpose

The scorecard turns agent evidence into a single fail-closed gate. It proves
that the project has controlled agent workflow depth beyond a plain retrieval
chain:

- routing and tool-use metrics from `artifacts/eval_agent/metrics.json`
- deterministic replay evidence from `artifacts/eval_agent_stress/replay.jsonl`
- HITL/checkpoint/thread-isolation stress metrics from
  `artifacts/eval_agent_stress/metrics.json`
- planner-executor scenario evidence from
  `artifacts/agent_orchestration/summary.json`
- audit evidence from `artifacts/eval_agent/agent_artifacts/audit.jsonl`

## Acceptance Thresholds

| metric | threshold | reason |
| --- | ---: | --- |
| `agent_lane_complete` | `1.0` | the base agent lane must be green |
| `routing_accuracy` | `>= 0.90` | route selection must be reliable |
| `tool_accuracy` | `>= 0.90` | metadata/tool route must be reliable |
| `rewrite_recovery` | `>= 0.80` | weak retrieval must recover rather than silently fail |
| `loop_termination` | `>= 1.0` | rewrite/reflection loop must be bounded |
| `trajectory_pass_rate` | `>= 1.0` | deterministic replay scenarios all pass |
| `branch_coverage` | `>= 1.0` | replay covers direct RAG, rewrite, abstain, tool, HITL, and thread reuse |
| `thread_id_isolation_pass` | `>= 1.0` | checkpoint reuse cannot leak stale state |
| `hitl_approval_convergence` | `>= 1.0` | approve and reject paths both terminate correctly |
| `no_side_effect_before_approval` | `>= 1.0` | save/export side effects wait for approval |
| `checkpoint_close_path_pass` | `>= 1.0` | checkpointer lifecycle is covered |
| `ops_tool_budget_violation_count` | `== 0` | tool-call budget is enforced |
| `planner_executor_or_supervisor_worker_pass` | `>= 1.0` | multi-step scenario evidence exists |
| `multi_tool_plan_pass` | `>= 1.0` | plan uses more than one tool class |
| `human_approval_node_pass` | `>= 1.0` | approval node is part of the workflow evidence |
| `required_replay_coverage` | `>= 1.0` | required replay rows are present and `ok=true` |
| `scenario_plan_count` | `>= 2` | at least two multi-step plans exist |
| `audit_line_count` | `>= 100` | audit surface is nontrivial |

## Important Non-claim

Planner-executor is claimed as scenario replay evidence over the current typed
LangGraph workflow. It is not claimed as a dynamic planner runtime or an
autonomous supervisor-worker production system.

That distinction matters for interview credibility: the repo proves state,
routes, retries, HITL, checkpoints, and tool boundaries today, while leaving a
dynamic planner runtime as a future product decision.
