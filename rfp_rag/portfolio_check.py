from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rfp_rag.gate_status import collect_gate_status
from rfp_rag.stage2_real import prediction_judge_coverage_summary


DEFERRED_GAPS = [
    {
        "id": "cloud_deployment",
        "reason": "external cloud credentials/spend are intentionally out of scope until approved",
    },
    {
        "id": "public_dashboard",
        "reason": "broad UI/dashboard scope requires a separate product decision",
    },
]

SECOND_STAGE_GATES = [
    {
        "id": "eval_stage2_coverage",
        "path": "artifacts/eval_stage2/coverage.json",
        "complete_field": "eval_set_audit_complete",
        "required_fields": (
            "eval_set_hash",
            "split_manifest_path",
            "label_rubric_path",
            "contamination_notes_path",
            "adjudication_log_path",
            "metrics",
            "thresholds",
            "failed",
        ),
        "metric_checks": (
            ("query_count", ">=", 150),
            ("metadata_doc_coverage", "==", 100),
            ("hard_negative_count", ">=", 30),
            ("cross_document_count", ">=", 20),
            ("visual_table_count", ">=", 30),
        ),
    },
    {
        "id": "eval_stage2_real",
        "path": "artifacts/eval_stage2_real/metrics.json",
        "complete_field": "holdout_quality_complete",
        "required_fields": (
            "contract_version",
            "required_command",
            "eval_set_hash",
            "query_set_counts",
            "thresholds_met",
            "per_slice_failed",
            "generation_model_id",
            "judge_model_id",
            "embedding_model_id",
            "prompt_template_hash",
            "metrics",
            "thresholds",
            "failed",
        ),
        "required_metric_fields": (
            "judge_coverage_faithfulness_min_by_answerable_slice",
            "judge_coverage_answer_relevancy_min_by_answerable_slice",
        ),
        "metric_checks": (
            ("recall@5", ">=", 0.95),
            ("recall@3", ">=", 0.90),
            ("mrr", ">=", 0.85),
            ("metadata_exact_match", ">=", 0.95),
            ("faithfulness", ">=", 0.90),
            ("answer_relevancy", ">=", 0.80),
            ("judge_coverage_faithfulness_min_by_answerable_slice", ">=", 0.95),
            ("judge_coverage_answer_relevancy_min_by_answerable_slice", ">=", 0.95),
            ("citation_presence", "==", 1.0),
            ("citation_validity", "==", 1.0),
        ),
    },
    {
        "id": "agent_stress",
        "path": "artifacts/eval_agent_stress/metrics.json",
        "complete_field": "agent_stress_complete",
        "required_fields": (
            "scenario_matrix_hash",
            "branch_replay_artifact_path",
            "metrics",
            "thresholds",
            "failed",
        ),
        "metric_checks": (
            ("trajectory_pass_rate", "==", 1.0),
            ("branch_coverage", "==", 1.0),
            ("thread_id_isolation_pass", "==", 1.0),
            ("hitl_approval_convergence", "==", 1.0),
            ("no_side_effect_before_approval", "==", 1.0),
            ("checkpoint_close_path_pass", "==", 1.0),
            ("audit_arg_redaction_pass", "==", 1.0),
            ("ops_tool_budget_violation_count", "==", 0),
        ),
    },
    {
        "id": "retrieval_bakeoff",
        "path": "artifacts/retrieval_bakeoff/summary.json",
        "complete_field": "retrieval_bakeoff_complete",
        "required_fields": (
            "decision",
            "comparison_set_hash",
            "compared_modes",
            "decision_adr_path",
            "metrics",
            "thresholds",
            "failed",
        ),
        "required_compared_modes": ("vector", "bm25", "hybrid_rrf"),
        "metric_checks": (
            ("recall_no_regression", "==", 1.0),
            ("citation_validity_no_regression", "==", 1.0),
            ("abstention_no_regression", "==", 1.0),
            ("section_hit_no_regression", "==", 1.0),
            ("visual_evidence_no_regression", "==", 1.0),
            ("latency_budget_pass", "==", 1.0),
            ("cost_budget_pass", "==", 1.0),
        ),
    },
    {
        "id": "visual_quality",
        "path": "artifacts/visual_quality/summary.json",
        "complete_field": "visual_quality_complete",
        "required_fields": ("metrics", "thresholds", "failed"),
        "metric_checks": (
            ("visual_question_count", ">=", 30),
            ("visual_evidence_hit_rate", ">=", 0.90),
            ("unsupported_visual_claim_rate", "<=", 0.10),
            ("sidecar_citation_no_regression", "==", 1.0),
            ("sidecar_abstention_no_regression", "==", 1.0),
        ),
    },
    {
        "id": "service_ops",
        "path": "artifacts/service_ops/summary.json",
        "complete_field": "service_ops_complete",
        "required_fields": (
            "docker_demo_command",
            "full_answer_smoke",
            "full_gates_smoke",
            "metrics",
            "thresholds",
            "failed",
        ),
        "metric_checks": (
            ("healthz_pass", "==", 1.0),
            ("answer_pass", "==", 1.0),
            ("stream_pass", "==", 1.0),
            ("gates_pass", "==", 1.0),
            ("ops_summary_pass", "==", 1.0),
            ("path_safety_pass", "==", 1.0),
            ("latency_p50_ms", ">=", 0.0),
            ("latency_p95_ms", ">=", 0.0),
            ("token_cost_distribution_recorded", "==", 1.0),
        ),
    },
    {
        "id": "security_redteam",
        "path": "artifacts/security_redteam/summary.json",
        "complete_field": "security_redteam_complete",
        "required_fields": (
            "publishable_allowlist_path",
            "retention_scope_path",
            "metrics",
            "thresholds",
            "failed",
        ),
        "metric_checks": (
            ("block_recall", "==", 1.0),
            ("malicious_document_pass", "==", 1.0),
            ("malicious_retrieved_evidence_pass", "==", 1.0),
            ("malicious_tool_output_pass", "==", 1.0),
            ("artifact_redaction_scan_pass", "==", 1.0),
            ("publishable_allowlist_pass", "==", 1.0),
            ("retention_scope_pass", "==", 1.0),
            ("secret_pii_leak_count", "==", 0),
            ("raw_persistence_count", "==", 0),
            ("tool_policy_violation_count", "==", 0),
        ),
    },
    {
        "id": "cost_budget",
        "path": "artifacts/cost_budget/summary.json",
        "complete_field": "cost_budget_complete",
        "required_fields": (
            "real_open_run_cost_estimate_usd",
            "regression_threshold_rationale",
            "metrics",
            "thresholds",
            "failed",
        ),
        "metric_checks": (
            ("token_record_coverage", "==", 1.0),
            ("cost_record_coverage", "==", 1.0),
            ("budget_violation_count", "==", 0),
        ),
    },
]

TOP_TIER_GATES = [
    {
        "id": "top_tier_roadmap",
        "path": "docs/portfolio/top-tier-roadmap.md",
        "kind": "document",
        "required_terms": (
            "Hosted or one-command reviewer demo",
            "Stage 3 independent holdout",
            "Real observability",
            "Upgraded agent orchestration",
            "Senior case study",
            "Failure conditions",
        ),
    },
    {
        "id": "reviewer_demo",
        "path": "artifacts/top_tier_demo/summary.json",
        "complete_field": "top_tier_demo_complete",
        "required_fields": (
            "demo_mode",
            "reviewer_command",
            "public_exposure_decision",
            "metrics",
            "thresholds",
            "failed",
        ),
        "metric_checks": (
            ("one_command_demo_pass", "==", 1.0),
            ("no_credentials_required", "==", 1.0),
            ("streaming_demo_pass", "==", 1.0),
            ("gate_summary_demo_pass", "==", 1.0),
            ("time_to_first_verified_answer_sec", "<=", 300.0),
        ),
    },
    {
        "id": "stage3_independent_holdout",
        "path": "artifacts/eval_stage3_holdout/metrics.json",
        "complete_field": "stage3_holdout_quality_complete",
        "required_fields": (
            "contract_version",
            "corpus_split_manifest_path",
            "label_rubric_path",
            "eval_set_hash",
            "query_set_counts",
            "metrics",
            "thresholds",
            "failed",
        ),
        "metric_checks": (
            ("document_count", ">=", 20),
            ("query_count", ">=", 100),
            ("recall@5", ">=", 0.90),
            ("mrr", ">=", 0.80),
            ("citation_validity", ">=", 0.95),
            ("faithfulness", ">=", 0.85),
            ("answer_relevancy", ">=", 0.78),
            ("unsupported_visual_claim_rate", "<=", 0.05),
            ("abstention_precision", ">=", 0.90),
        ),
    },
    {
        "id": "real_observability",
        "path": "artifacts/observability/summary.json",
        "complete_field": "observability_complete",
        "required_fields": (
            "trace_provider",
            "trace_export_path",
            "failed_run_analysis_path",
            "metrics",
            "thresholds",
            "failed",
        ),
        "metric_checks": (
            ("trace_export_present", "==", 1.0),
            ("latency_p50_ms_recorded", "==", 1.0),
            ("latency_p95_ms_recorded", "==", 1.0),
            ("token_cost_recorded", "==", 1.0),
            ("tool_success_rate_recorded", "==", 1.0),
            ("failed_run_analysis_count", ">=", 5),
        ),
    },
    {
        "id": "upgraded_agent_orchestration",
        "path": "artifacts/agent_orchestration/summary.json",
        "complete_field": "agent_orchestration_upgrade_complete",
        "required_fields": (
            "architecture_pattern",
            "scenario_matrix_path",
            "metrics",
            "thresholds",
            "failed",
        ),
        "metric_checks": (
            ("planner_executor_or_supervisor_worker_pass", "==", 1.0),
            ("multi_tool_plan_pass", "==", 1.0),
            ("bounded_retry_reflection_pass", "==", 1.0),
            ("human_approval_node_pass", "==", 1.0),
            ("state_schema_validation_pass", "==", 1.0),
        ),
    },
    {
        "id": "security_reliability_deepening",
        "path": "artifacts/reliability_security/summary.json",
        "complete_field": "security_reliability_complete",
        "required_fields": (
            "redteam_suite_path",
            "reliability_suite_path",
            "metrics",
            "thresholds",
            "failed",
        ),
        "metric_checks": (
            ("redteam_case_count", ">=", 20),
            ("prompt_injection_block_recall", "==", 1.0),
            ("secrets_pii_leak_count", "==", 0),
            ("fallback_recovery_pass", "==", 1.0),
            ("deterministic_replay_pass", "==", 1.0),
        ),
    },
    {
        "id": "senior_case_study",
        "path": "docs/portfolio/case-study.md",
        "kind": "document",
        "required_terms": (
            "Problem",
            "Architecture decisions",
            "Evaluation evidence",
            "Failure analysis",
            "Operational boundaries",
            "Interview defense",
        ),
    },
    {
        "id": "deployment_readiness",
        "path": "artifacts/deployment_readiness/summary.json",
        "complete_field": "deployment_readiness_complete",
        "required_fields": (
            "deployment_mode",
            "hosted_deployment_plan_path",
            "public_deployment_decision",
            "auth_boundary",
            "rate_limit_boundary",
            "secret_handling_boundary",
            "metrics",
            "thresholds",
            "failed",
        ),
        "metric_checks": (
            ("auth_boundary_documented", "==", 1.0),
            ("rate_limit_plan_documented", "==", 1.0),
            ("secret_handling_documented", "==", 1.0),
            ("public_exposure_requires_approval", "==", 1.0),
            ("one_command_fallback_documented", "==", 1.0),
        ),
    },
    {
        "id": "interview_demo_package",
        "path": "artifacts/interview_demo_package/summary.json",
        "complete_field": "interview_demo_package_complete",
        "required_fields": (
            "storyboard_path",
            "generated_artifact_paths",
            "reviewer_time_budget_minutes",
            "demo_duration_minutes",
            "metrics",
            "thresholds",
            "failed",
        ),
        "metric_checks": (
            ("three_minute_storyboard_present", "==", 1.0),
            ("generated_artifact_count", ">=", 4.0),
            ("one_command_path_documented", "==", 1.0),
            ("ten_minute_reviewer_path_documented", "==", 1.0),
            ("security_observability_evidence_mapped", "==", 1.0),
        ),
    },
    {
        "id": "dependency_security",
        "path": "artifacts/security_alerts/summary.json",
        "complete_field": "dependency_security_complete",
        "required_fields": (
            "risk_register_path",
            "remediated_alerts",
            "open_alerts",
            "residual_risk_approval",
            "metrics",
            "thresholds",
            "failed",
        ),
        "metric_checks": (
            ("langchain_patched", "==", 1.0),
            ("diskcache_absent", "==", 1.0),
            ("unresolved_unaccepted_alert_count", "==", 0),
        ),
    },
]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _check_file(root: Path, rel: str) -> dict[str, Any]:
    path = root / rel
    check_id = (
        rel.replace("/", "_").replace(".", "_").replace("-", "_").strip("_").lower()
    )
    return {"id": check_id, "ok": path.is_file(), "path": rel}


def _check_text(root: Path, rel: str, needle: str, check_id: str) -> dict[str, Any]:
    path = root / rel
    ok = path.is_file() and needle in path.read_text(encoding="utf-8")
    return {"id": check_id, "ok": ok, "path": rel, "needle": needle}


def _check_paid_lane_plan(root: Path) -> dict[str, Any]:
    rel = "artifacts/paid_lane_plan/summary.json"
    summary = _read_json(root / rel)
    required_steps = {
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
    }
    step_ids = {
        str(step.get("id"))
        for step in summary.get("steps", [])
        if isinstance(step, dict)
    }
    ok = (
        summary.get("paid_lane_plan_complete") is True
        and summary.get("approval_required") is True
        and summary.get("does_not_execute_paid_lanes") is True
        and "OPENAI_API_KEY" in (summary.get("required_env_vars") or [])
        and required_steps <= step_ids
    )
    return {
        "id": "paid_lane_plan",
        "ok": ok,
        "path": rel,
        "required_steps": sorted(required_steps),
        "present_steps": sorted(step_ids),
    }


def _second_stage_gate_issues(
    gate: dict[str, Any],
    summary: dict[str, Any],
    coverage_hash: str | None,
    root: Path,
) -> list[str]:
    issues: list[str] = []
    complete_field = gate["complete_field"]
    if summary.get(complete_field) is not True:
        issues.append(complete_field)
    for field in gate.get("required_fields", ()):
        if field not in summary or summary.get(field) in (None, ""):
            issues.append(field)
    failed = summary.get("failed")
    if failed:
        issues.append("failed")
    metrics = summary.get("metrics")
    thresholds = summary.get("thresholds")
    if not isinstance(metrics, dict):
        issues.append("metrics")
        metrics = {}
    if not isinstance(thresholds, dict):
        issues.append("thresholds")
        thresholds = {}
    for field, op, expected in gate.get("metric_checks", ()):
        value = metrics.get(field)
        if value is None or not _metric_passes(value, op, expected):
            issues.append(field)
        threshold = thresholds.get(field)
        if threshold is None or not _threshold_matches(threshold, op, expected):
            issues.append(f"threshold:{field}")
    required_modes = set(gate.get("required_compared_modes", ()))
    if required_modes:
        actual_modes = summary.get("compared_modes")
        if not isinstance(actual_modes, list) or not required_modes <= set(
            str(mode) for mode in actual_modes
        ):
            issues.append("compared_modes")
    if gate["id"] == "eval_stage2_real":
        if summary.get("thresholds_met") is not True:
            issues.append("thresholds_met")
        if summary.get("contract_version") != "rfp-rag-stage2-real-v1":
            issues.append("contract_version")
        required_command = str(summary.get("required_command") or "")
        if "--out artifacts/eval_stage2_real" not in required_command:
            issues.append("required_command")
        if summary.get("per_slice_failed") != []:
            issues.append("per_slice_failed")
        if coverage_hash and summary.get("eval_set_hash") != coverage_hash:
            issues.append("eval_set_hash_mismatch")
        prediction_coverage = prediction_judge_coverage_summary(
            root / "artifacts/eval_stage2_real/predictions.jsonl",
            _read_json(root / "artifacts/eval_stage2/coverage.json"),
        )
        if prediction_coverage.get("ok") is not True:
            issues.extend(prediction_coverage.get("issues") or [])
        summary_prediction_coverage = summary.get("prediction_judge_coverage")
        if not isinstance(summary_prediction_coverage, dict):
            issues.append("prediction_judge_coverage")
        else:
            for field in (
                "counts_by_slice",
                "faithfulness_min_by_answerable_slice",
                "answer_relevancy_min_by_answerable_slice",
            ):
                if summary_prediction_coverage.get(field) != prediction_coverage.get(
                    field
                ):
                    issues.append(f"prediction_judge_coverage.{field}")
        coverage_counts = _read_json(root / "artifacts/eval_stage2/coverage.json").get(
            "counts_by_slice", {}
        )
        if isinstance(coverage_counts, dict) and coverage_counts:
            raw_counts = summary.get("query_set_counts")
            if not isinstance(raw_counts, dict):
                issues.append("query_set_counts")
            else:
                expected_total = sum(
                    int(value)
                    for value in coverage_counts.values()
                    if isinstance(value, int | float)
                )
                if raw_counts.get("total") != expected_total:
                    issues.append("query_set_counts.total")
                for coverage_key, raw_key in {
                    "metadata": "golden_metadata",
                    "curated_text": "curated_text",
                    "section_lookup": "section_lookup",
                    "cross_document": "cross_document",
                    "visual_table": "visual_table",
                    "paraphrase": "paraphrase",
                    "abstention": "abstention",
                }.items():
                    if coverage_key in coverage_counts and raw_counts.get(
                        raw_key
                    ) != coverage_counts.get(coverage_key):
                        issues.append(f"query_set_counts.{raw_key}")
        for field in gate.get("required_metric_fields", ()):
            if metrics.get(field) is None:
                issues.append(field)
        prompt_hash = summary.get("prompt_template_hash")
        if not isinstance(prompt_hash, str) or len(prompt_hash) != 64:
            issues.append("prompt_template_hash")
    if gate["id"] == "eval_stage2_coverage":
        issues.extend(_stage2_support_issues(root, summary, coverage_hash))
    if gate["id"] == "service_ops":
        if summary.get("full_answer_smoke") is not True:
            issues.append("full_answer_smoke")
        if summary.get("full_gates_smoke") is not True:
            issues.append("full_gates_smoke")
    return sorted(set(issues))


def _read_support_text(root: Path, rel: str) -> str:
    path = root / rel
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _stage2_support_issues(
    root: Path, summary: dict[str, Any], coverage_hash: str | None
) -> list[str]:
    issues: list[str] = []
    split_rel = str(summary.get("split_manifest_path") or "")
    split = _read_json(root / split_rel) if split_rel else {}
    if split.get("policy") != "frozen_stage2_evidence_set":
        issues.append("split_manifest_policy")
    if split.get("train_dev_holdout_separation_complete") is not True:
        issues.append("train_dev_holdout_separation_complete")
    if coverage_hash and split.get("eval_set_hash") != coverage_hash:
        issues.append("split_manifest_eval_set_hash")
    if split.get("tuning_after_freeze_allowed") is not False:
        issues.append("tuning_after_freeze_allowed")

    label_text = _read_support_text(root, str(summary.get("label_rubric_path") or ""))
    if "TODO" in label_text or "Freeze key" not in label_text:
        issues.append("label_rubric")
    contamination_text = _read_support_text(
        root, str(summary.get("contamination_notes_path") or "")
    )
    if "TODO" in contamination_text or "eval-set hash" not in contamination_text:
        issues.append("contamination_notes")

    adjudication_rel = str(summary.get("adjudication_log_path") or "")
    adjudication_path = root / adjudication_rel
    if not adjudication_rel or not adjudication_path.exists():
        issues.append("adjudication_log_path")
    return issues


def _metric_passes(value: Any, op: str, expected: int | float) -> bool:
    if not isinstance(value, int | float):
        return False
    if op == ">=":
        return value >= expected
    if op == "<=":
        return value <= expected
    if op == "==":
        return value == expected
    raise ValueError(f"unsupported metric operator: {op!r}")


def _threshold_matches(value: Any, op: str, expected: int | float) -> bool:
    if not isinstance(value, int | float):
        return False
    # Thresholds define the same floor/ceiling/equality that metrics are checked against.
    return value == expected


def _collect_second_stage_readiness(root: Path) -> dict[str, Any]:
    present: list[str] = []
    missing: list[str] = []
    failed: list[str] = []
    details: list[dict[str, Any]] = []
    coverage_summary = _read_json(root / "artifacts/eval_stage2/coverage.json")
    coverage_hash = coverage_summary.get("eval_set_hash")
    if not isinstance(coverage_hash, str) or not coverage_hash:
        coverage_hash = None
    for gate in SECOND_STAGE_GATES:
        path = root / gate["path"]
        if not path.exists():
            missing.append(gate["id"])
            details.append({**gate, "present": False, "ok": False})
            continue
        summary = _read_json(path)
        issues = _second_stage_gate_issues(gate, summary, coverage_hash, root)
        ok = not issues
        present.append(gate["id"])
        if not ok:
            failed.append(gate["id"])
        details.append(
            {
                **gate,
                "present": True,
                "ok": ok,
                "issues": issues,
                "failed": summary.get("failed") or [],
            }
        )
    return {
        "complete": not missing and not failed,
        "schema_enforced": not missing and not failed,
        "present": present,
        "missing": missing,
        "failed": failed,
        "details": details,
    }


def _top_tier_gate_issues(gate: dict[str, Any], summary: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    complete_field = gate.get("complete_field")
    if complete_field and summary.get(complete_field) is not True:
        issues.append(str(complete_field))
    for field in gate.get("required_fields", ()):
        if field not in summary or summary.get(field) in (None, ""):
            issues.append(field)
    failed = summary.get("failed")
    if failed:
        issues.append("failed")
    metrics = summary.get("metrics")
    thresholds = summary.get("thresholds")
    if not isinstance(metrics, dict):
        issues.append("metrics")
        metrics = {}
    if not isinstance(thresholds, dict):
        issues.append("thresholds")
        thresholds = {}
    for field, op, expected in gate.get("metric_checks", ()):
        value = metrics.get(field)
        if value is None or not _metric_passes(value, op, expected):
            issues.append(field)
        threshold = thresholds.get(field)
        if threshold is None or not _threshold_matches(threshold, op, expected):
            issues.append(f"threshold:{field}")
    return sorted(set(issues))


def _document_gate_issues(root: Path, gate: dict[str, Any]) -> list[str]:
    text = _read_support_text(root, str(gate["path"]))
    issues: list[str] = []
    if not text:
        issues.append("document_missing")
    for term in gate.get("required_terms", ()):
        if term not in text:
            issues.append(f"term:{term}")
    return issues


def _collect_top_tier_readiness(root: Path) -> dict[str, Any]:
    present: list[str] = []
    missing: list[str] = []
    failed: list[str] = []
    details: list[dict[str, Any]] = []
    for gate in TOP_TIER_GATES:
        path = root / gate["path"]
        if not path.exists():
            missing.append(gate["id"])
            details.append({**gate, "present": False, "ok": False})
            continue
        if gate.get("kind") == "document":
            issues = _document_gate_issues(root, gate)
            summary_failed: list[str] = []
        else:
            summary = _read_json(path)
            issues = _top_tier_gate_issues(gate, summary)
            summary_failed = summary.get("failed") or []
        ok = not issues
        present.append(gate["id"])
        if not ok:
            failed.append(gate["id"])
        details.append(
            {
                **gate,
                "present": True,
                "ok": ok,
                "issues": issues,
                "failed": summary_failed,
            }
        )
    return {
        "complete": not missing and not failed,
        "present": present,
        "missing": missing,
        "failed": failed,
        "details": details,
    }


def collect_portfolio_readiness(root: Path = Path(".")) -> dict[str, Any]:
    root = root.resolve()
    checks: list[dict[str, Any]] = []

    gate_status = collect_gate_status(root)
    checks.append(
        {
            "id": "gate_status",
            "ok": bool(gate_status.get("overall_ok")),
            "path": "python3 -m rfp_rag.gate_status",
        }
    )

    guardrail = _read_json(root / "artifacts/guardrails/summary.json")
    checks.append(
        {
            "id": "guardrail_regression",
            "ok": bool(guardrail.get("guardrail_regression_complete")),
            "path": "artifacts/guardrails/summary.json",
            "metrics": guardrail.get("metrics") or {},
        }
    )

    checks.extend(
        [
            _check_file(root, "Dockerfile"),
            _check_file(root, ".github/workflows/ci.yml"),
            _check_file(root, "docs/architecture/system-architecture.md"),
            _check_text(
                root,
                "docs/portfolio/senior-reviewer-pack.md",
                "10-minute Review Path",
                "senior_reviewer_pack_path",
            ),
            _check_text(
                root,
                "docs/portfolio/senior-reviewer-pack.md",
                "Scorecard Target",
                "senior_reviewer_pack_scorecard",
            ),
            _check_text(
                root,
                "docs/portfolio/company-fit-matrix.md",
                "Tier A 21 roles and Tier B 107 roles",
                "company_fit_matrix_tier_snapshot",
            ),
            _check_text(
                root,
                "docs/portfolio/company-fit-matrix.md",
                "AI Agent Platform Engineering",
                "company_fit_matrix_agent_platform",
            ),
            _check_file(root, "docs/adr/0014-fastapi-service-surface.md"),
            _check_file(root, "docs/adr/0015-docker-ci-baseline.md"),
            _check_file(root, "docs/adr/0016-mcp-style-ops-tool-server.md"),
            _check_text(
                root,
                "README.md",
                "docs/architecture/system-architecture.md",
                "readme_architecture_link",
            ),
            _check_text(
                root,
                "README.md",
                "docs/portfolio/senior-reviewer-pack.md",
                "readme_senior_reviewer_pack_link",
            ),
            _check_text(
                root,
                "README.md",
                "docs/portfolio/company-fit-matrix.md",
                "readme_company_fit_matrix_link",
            ),
            _check_text(
                root,
                "REPORT.md",
                "Architecture evidence map",
                "report_architecture_section",
            ),
            _check_text(
                root,
                ".github/workflows/ci.yml",
                'pytest -m "not real"',
                "ci_no_real_tests",
            ),
            _check_text(
                root,
                ".github/workflows/ci.yml",
                "docker build",
                "ci_docker_build",
            ),
            _check_paid_lane_plan(root),
        ]
    )

    failed = [check for check in checks if not check["ok"]]
    second_stage = _collect_second_stage_readiness(root)
    top_tier = _collect_top_tier_readiness(root)
    local_evidence_bundle_check = not failed
    stage2_contract_schema_enforced = bool(second_stage["schema_enforced"])
    portfolio_readiness_check = local_evidence_bundle_check and bool(
        second_stage["complete"] and stage2_contract_schema_enforced
    )
    interview_readiness_check = portfolio_readiness_check and bool(top_tier["complete"])
    return {
        "portfolio_readiness_check": portfolio_readiness_check,
        "interview_readiness_check": interview_readiness_check,
        "local_evidence_bundle_check": local_evidence_bundle_check,
        "stage2_contract_schema_enforced": stage2_contract_schema_enforced,
        "root": str(root),
        "checks": checks,
        "failed": failed,
        "second_stage_readiness": second_stage,
        "top_tier_readiness": top_tier,
        "deferred": [gap["id"] for gap in DEFERRED_GAPS],
        "deferred_details": DEFERRED_GAPS,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check local senior-portfolio evidence bundle readiness."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--out", type=Path, default=Path("artifacts/portfolio_readiness.json")
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    report = collect_portfolio_readiness(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if report["interview_readiness_check"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
