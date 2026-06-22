from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.portfolio_check import collect_portfolio_readiness, main


def _write(path: Path, text: str = "ok") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _minimal_ready_root(root: Path) -> None:
    _write(
        root / "README.md",
        "\n".join(
            [
                "docs/architecture/system-architecture.md",
                "docs/portfolio/senior-reviewer-pack.md",
                "docs/portfolio/company-fit-matrix.md",
            ]
        ),
    )
    _write(root / "REPORT.md", "Architecture evidence map\n")
    _write(root / "Dockerfile", "FROM python:3.13-slim\n")
    _write(
        root / ".github/workflows/ci.yml",
        'uv run pytest -m "not real"\ndocker build -t rfp-rag-service:ci .\n',
    )
    _write(
        root / "docs/architecture/system-architecture.md", "## Operational Boundaries\n"
    )
    _write(
        root / "docs/portfolio/senior-reviewer-pack.md",
        "10-minute Review Path\nScorecard Target\n",
    )
    _write(
        root / "docs/portfolio/company-fit-matrix.md",
        "Tier A 21 roles and Tier B 107 roles\nAI Agent Platform Engineering\n",
    )
    _write(root / "docs/adr/0014-fastapi-service-surface.md")
    _write(root / "docs/adr/0015-docker-ci-baseline.md")
    _write(root / "docs/adr/0016-mcp-style-ops-tool-server.md")
    _write(
        root / "artifacts/guardrails/summary.json",
        json.dumps(
            {
                "guardrail_regression_complete": True,
                "case_count": 7,
                "passed": 7,
                "failed": 0,
                "metrics": {
                    "block_recall": 1.0,
                    "allow_recall": 1.0,
                    "category_exact_match": 1.0,
                },
            }
        ),
    )
    _write(
        root / "artifacts/paid_lane_plan/summary.json",
        json.dumps(
            {
                "paid_lane_plan_complete": True,
                "approval_required": True,
                "does_not_execute_paid_lanes": True,
                "required_env_vars": ["OPENAI_API_KEY"],
                "steps": [
                    {"id": "real_index_v6"},
                    {"id": "real_eval_v6"},
                    {"id": "stage2_real_eval"},
                    {"id": "stage2_real_finalize"},
                    {"id": "stage3_holdout_case_freeze"},
                    {"id": "stage3_real_eval"},
                    {"id": "stage3_holdout_finalize"},
                    {"id": "same_set_open_reranker_eval"},
                    {"id": "retrieval_bakeoff"},
                    {"id": "cost_budget"},
                    {"id": "gate_status"},
                    {"id": "portfolio_check"},
                ],
            }
        ),
    )


def _write_complete_second_stage(root: Path) -> None:
    eval_set_hash = "stage2-eval-set-v1"
    prediction_judge_coverage = {
        "ok": True,
        "path": str(root / "artifacts/eval_stage2_real/predictions.jsonl"),
        "issues": [],
        "counts_by_slice": {"metadata": 1},
        "faithfulness_by_slice": {"metadata": 1.0},
        "answer_relevancy_by_slice": {"metadata": 1.0},
        "faithfulness_min_by_answerable_slice": 1.0,
        "answer_relevancy_min_by_answerable_slice": 1.0,
    }
    complete_payloads = {
        "artifacts/eval_stage2/coverage.json": {
            "eval_set_audit_complete": True,
            "eval_set_hash": eval_set_hash,
            "split_manifest_path": "artifacts/eval_stage2/split_manifest.json",
            "label_rubric_path": "artifacts/eval_stage2/label_rubric.md",
            "contamination_notes_path": "artifacts/eval_stage2/contamination_notes.md",
            "adjudication_log_path": "artifacts/eval_stage2/adjudication.jsonl",
            "thresholds": {
                "query_count": 150,
                "metadata_doc_coverage": 100,
                "hard_negative_count": 30,
                "cross_document_count": 20,
                "visual_table_count": 30,
            },
            "metrics": {
                "query_count": 150,
                "metadata_doc_coverage": 100,
                "hard_negative_count": 30,
                "cross_document_count": 20,
                "visual_table_count": 30,
            },
            "failed": [],
        },
        "artifacts/eval_stage2_real/metrics.json": {
            "holdout_quality_complete": True,
            "contract_version": "rfp-rag-stage2-real-v1",
            "required_command": (
                "python3 -m rfp_rag.evaluate --data data/data_list.csv "
                "--index artifacts/index_real --out artifacts/eval_stage2_real "
                "--provider real_openai"
            ),
            "eval_set_hash": eval_set_hash,
            "thresholds_met": True,
            "per_slice_failed": [],
            "generation_model_id": "gpt-test",
            "judge_model_id": "judge-test",
            "embedding_model_id": "embed-test",
            "prompt_template_hash": "a" * 64,
            "query_set_counts": {
                "total": 150,
                "golden_metadata": 100,
                "abstention": 30,
                "cross_document": 20,
                "visual_table": 30,
            },
            "prediction_judge_coverage": prediction_judge_coverage,
            "metrics": {
                "recall@5": 0.95,
                "recall@3": 0.90,
                "mrr": 0.85,
                "metadata_exact_match": 0.95,
                "faithfulness": 0.90,
                "answer_relevancy": 0.80,
                "judge_coverage_faithfulness_min_by_answerable_slice": 0.95,
                "judge_coverage_answer_relevancy_min_by_answerable_slice": 0.95,
                "citation_presence": 1.0,
                "citation_validity": 1.0,
            },
            "thresholds": {
                "recall@5": 0.95,
                "recall@3": 0.90,
                "mrr": 0.85,
                "metadata_exact_match": 0.95,
                "faithfulness": 0.90,
                "answer_relevancy": 0.80,
                "judge_coverage_faithfulness_min_by_answerable_slice": 0.95,
                "judge_coverage_answer_relevancy_min_by_answerable_slice": 0.95,
                "citation_presence": 1.0,
                "citation_validity": 1.0,
            },
            "failed": [],
        },
        "artifacts/eval_agent_stress/metrics.json": {
            "agent_stress_complete": True,
            "scenario_matrix_hash": "b" * 64,
            "branch_replay_artifact_path": "artifacts/eval_agent_stress/replay.jsonl",
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
            "thresholds": {
                "trajectory_pass_rate": 1.0,
                "branch_coverage": 1.0,
                "thread_id_isolation_pass": 1.0,
                "hitl_approval_convergence": 1.0,
                "no_side_effect_before_approval": 1.0,
                "checkpoint_close_path_pass": 1.0,
                "audit_arg_redaction_pass": 1.0,
                "ops_tool_budget_violation_count": 0,
            },
            "failed": [],
        },
        "artifacts/retrieval_bakeoff/summary.json": {
            "retrieval_bakeoff_complete": True,
            "decision": "keep_vector_until_reranker_wins",
            "comparison_set_hash": eval_set_hash,
            "compared_modes": ["vector", "bm25", "hybrid_rrf", "reranker"],
            "decision_adr_path": "docs/adr/0020-retrieval-bakeoff.md",
            "metrics": {
                "recall_no_regression": 1.0,
                "citation_validity_no_regression": 1.0,
                "abstention_no_regression": 1.0,
                "section_hit_no_regression": 1.0,
                "visual_evidence_no_regression": 1.0,
                "latency_budget_pass": 1.0,
                "cost_budget_pass": 1.0,
            },
            "thresholds": {
                "recall_no_regression": 1.0,
                "citation_validity_no_regression": 1.0,
                "abstention_no_regression": 1.0,
                "section_hit_no_regression": 1.0,
                "visual_evidence_no_regression": 1.0,
                "latency_budget_pass": 1.0,
                "cost_budget_pass": 1.0,
            },
            "failed": [],
        },
        "artifacts/visual_quality/summary.json": {
            "visual_quality_complete": True,
            "metrics": {
                "visual_question_count": 30,
                "visual_evidence_hit_rate": 0.9,
                "unsupported_visual_claim_rate": 0.1,
                "sidecar_citation_no_regression": 1.0,
                "sidecar_abstention_no_regression": 1.0,
            },
            "thresholds": {
                "visual_question_count": 30,
                "visual_evidence_hit_rate": 0.9,
                "unsupported_visual_claim_rate": 0.1,
                "sidecar_citation_no_regression": 1.0,
                "sidecar_abstention_no_regression": 1.0,
            },
            "failed": [],
        },
        "artifacts/service_ops/summary.json": {
            "service_ops_complete": True,
            "docker_demo_command": "docker run --rm rfp-rag-service:ci",
            "full_answer_smoke": True,
            "full_gates_smoke": True,
            "metrics": {
                "healthz_pass": 1.0,
                "answer_pass": 1.0,
                "stream_pass": 1.0,
                "gates_pass": 1.0,
                "ops_summary_pass": 1.0,
                "path_safety_pass": 1.0,
                "latency_p50_ms": 100.0,
                "latency_p95_ms": 250.0,
                "token_cost_distribution_recorded": 1.0,
            },
            "thresholds": {
                "healthz_pass": 1.0,
                "answer_pass": 1.0,
                "stream_pass": 1.0,
                "gates_pass": 1.0,
                "ops_summary_pass": 1.0,
                "path_safety_pass": 1.0,
                "latency_p50_ms": 0.0,
                "latency_p95_ms": 0.0,
                "token_cost_distribution_recorded": 1.0,
            },
            "failed": [],
        },
        "artifacts/security_redteam/summary.json": {
            "security_redteam_complete": True,
            "publishable_allowlist_path": "docs/evidence/publishable-artifacts.md",
            "retention_scope_path": "docs/evidence/artifact-retention.md",
            "metrics": {
                "block_recall": 1.0,
                "malicious_document_pass": 1.0,
                "malicious_retrieved_evidence_pass": 1.0,
                "malicious_tool_output_pass": 1.0,
                "artifact_redaction_scan_pass": 1.0,
                "publishable_allowlist_pass": 1.0,
                "retention_scope_pass": 1.0,
                "secret_pii_leak_count": 0,
                "raw_persistence_count": 0,
                "tool_policy_violation_count": 0,
            },
            "thresholds": {
                "block_recall": 1.0,
                "malicious_document_pass": 1.0,
                "malicious_retrieved_evidence_pass": 1.0,
                "malicious_tool_output_pass": 1.0,
                "artifact_redaction_scan_pass": 1.0,
                "publishable_allowlist_pass": 1.0,
                "retention_scope_pass": 1.0,
                "secret_pii_leak_count": 0,
                "raw_persistence_count": 0,
                "tool_policy_violation_count": 0,
            },
            "failed": [],
        },
        "artifacts/cost_budget/summary.json": {
            "cost_budget_complete": True,
            "real_open_run_cost_estimate_usd": 5.0,
            "regression_threshold_rationale": "initial budget cap",
            "metrics": {
                "token_record_coverage": 1.0,
                "cost_record_coverage": 1.0,
                "budget_violation_count": 0,
            },
            "thresholds": {
                "token_record_coverage": 1.0,
                "cost_record_coverage": 1.0,
                "budget_violation_count": 0,
            },
            "failed": [],
        },
    }
    for rel, payload in complete_payloads.items():
        _write(root / rel, json.dumps(payload))
    _write(
        root / "artifacts/eval_stage2_real/predictions.jsonl",
        json.dumps(
            {
                "query_id": "metadata_budget_000",
                "judge": {"faithfulness": 1.0, "answer_relevancy": 1.0},
            }
        )
        + "\n",
    )
    _write(
        root / "artifacts/eval_stage2/split_manifest.json",
        json.dumps(
            {
                "eval_set_hash": eval_set_hash,
                "policy": "frozen_stage2_evidence_set",
                "train_dev_holdout_separation_complete": True,
                "tuning_after_freeze_allowed": False,
            }
        ),
    )
    _write(
        root / "artifacts/eval_stage2/label_rubric.md",
        "# Stage 2 Label Rubric\n\n- Freeze key: eval_set_hash.\n",
    )
    _write(
        root / "artifacts/eval_stage2/contamination_notes.md",
        "# Stage 2 Contamination Notes\n\n- eval-set hash controls the freeze boundary.\n",
    )
    _write(root / "artifacts/eval_stage2/adjudication.jsonl", "")


def _write_complete_top_tier(root: Path) -> None:
    _write(
        root / "docs/portfolio/top-tier-roadmap.md",
        "\n".join(
            [
                "# Top-tier roadmap",
                "Hosted or one-command reviewer demo",
                "Stage 3 independent holdout",
                "Real observability",
                "Upgraded agent orchestration",
                "Senior case study",
                "Failure conditions",
            ]
        ),
    )
    _write(
        root / "docs/portfolio/case-study.md",
        "\n".join(
            [
                "# Case study",
                "Problem",
                "Architecture decisions",
                "Evaluation evidence",
                "Failure analysis",
                "Operational boundaries",
                "Interview defense",
            ]
        ),
    )
    top_tier_payloads = {
        "artifacts/top_tier_demo/summary.json": {
            "top_tier_demo_complete": True,
            "demo_mode": "one-command",
            "reviewer_command": "uv run python -m rfp_rag.top_tier_demo",
            "public_exposure_decision": "local_only",
            "metrics": {
                "one_command_demo_pass": 1.0,
                "no_credentials_required": 1.0,
                "streaming_demo_pass": 1.0,
                "gate_summary_demo_pass": 1.0,
                "time_to_first_verified_answer_sec": 300.0,
            },
            "thresholds": {
                "one_command_demo_pass": 1.0,
                "no_credentials_required": 1.0,
                "streaming_demo_pass": 1.0,
                "gate_summary_demo_pass": 1.0,
                "time_to_first_verified_answer_sec": 300.0,
            },
            "failed": [],
        },
        "artifacts/eval_stage3_holdout/metrics.json": {
            "stage3_holdout_quality_complete": True,
            "contract_version": "rfp-rag-stage3-holdout-v1",
            "corpus_split_manifest_path": "artifacts/eval_stage3_holdout/split_manifest.json",
            "label_rubric_path": "artifacts/eval_stage3_holdout/label_rubric.md",
            "eval_set_hash": "stage3-hash",
            "query_set_counts": {"total": 100},
            "metrics": {
                "document_count": 20,
                "query_count": 100,
                "recall@5": 0.90,
                "mrr": 0.80,
                "citation_validity": 0.95,
                "faithfulness": 0.85,
                "answer_relevancy": 0.78,
                "unsupported_visual_claim_rate": 0.05,
                "abstention_precision": 0.90,
            },
            "thresholds": {
                "document_count": 20,
                "query_count": 100,
                "recall@5": 0.90,
                "mrr": 0.80,
                "citation_validity": 0.95,
                "faithfulness": 0.85,
                "answer_relevancy": 0.78,
                "unsupported_visual_claim_rate": 0.05,
                "abstention_precision": 0.90,
            },
            "failed": [],
        },
        "artifacts/stage2_quality_scorecard/summary.json": {
            "stage2_quality_scorecard_complete": True,
            "evidence_paths": {
                "parser_quality": "artifacts/parser_quality/summary.json"
            },
            "metrics": {
                "parser_doc_count": 100,
                "parser_average_quality_score": 0.95,
                "parser_page_citation_coverage": 1.0,
                "parser_low_quality_doc_count": 0,
                "stage2_query_count": 150,
                "stage3_query_count": 100,
                "context_precision_at5": 0.9,
                "context_recall_at5": 0.9,
                "citation_precision_proxy": 0.95,
                "unsupported_claim_rate": 0.0,
                "stage3_faithfulness": 0.9,
                "stage3_answer_relevancy": 0.86,
                "retrieval_no_regression": 1.0,
                "visual_evidence_hit_rate": 0.92,
            },
            "thresholds": {
                "parser_doc_count": 100,
                "parser_average_quality_score": 0.90,
                "parser_page_citation_coverage": 1.0,
                "parser_low_quality_doc_count": 0,
                "stage2_query_count": 150,
                "stage3_query_count": 100,
                "context_precision_at5": 0.70,
                "context_recall_at5": 0.75,
                "citation_precision_proxy": 0.90,
                "unsupported_claim_rate": 0.03,
                "stage3_faithfulness": 0.85,
                "stage3_answer_relevancy": 0.85,
                "retrieval_no_regression": 1.0,
                "visual_evidence_hit_rate": 0.90,
            },
            "failed": [],
        },
        "artifacts/observability/summary.json": {
            "observability_complete": True,
            "trace_provider": "phoenix",
            "trace_export_path": "artifacts/observability/traces.jsonl",
            "failed_run_analysis_path": "docs/portfolio/failed-run-analysis.md",
            "metrics": {
                "trace_export_present": 1.0,
                "latency_p50_ms_recorded": 1.0,
                "latency_p95_ms_recorded": 1.0,
                "token_cost_recorded": 1.0,
                "tool_success_rate_recorded": 1.0,
                "failed_run_analysis_count": 5,
            },
            "thresholds": {
                "trace_export_present": 1.0,
                "latency_p50_ms_recorded": 1.0,
                "latency_p95_ms_recorded": 1.0,
                "token_cost_recorded": 1.0,
                "tool_success_rate_recorded": 1.0,
                "failed_run_analysis_count": 5,
            },
            "failed": [],
        },
        "artifacts/agent_orchestration/summary.json": {
            "agent_orchestration_upgrade_complete": True,
            "architecture_pattern": "planner-executor",
            "scenario_matrix_path": "artifacts/agent_orchestration/scenarios.jsonl",
            "metrics": {
                "planner_executor_or_supervisor_worker_pass": 1.0,
                "multi_tool_plan_pass": 1.0,
                "bounded_retry_reflection_pass": 1.0,
                "human_approval_node_pass": 1.0,
                "state_schema_validation_pass": 1.0,
            },
            "thresholds": {
                "planner_executor_or_supervisor_worker_pass": 1.0,
                "multi_tool_plan_pass": 1.0,
                "bounded_retry_reflection_pass": 1.0,
                "human_approval_node_pass": 1.0,
                "state_schema_validation_pass": 1.0,
            },
            "failed": [],
        },
        "artifacts/stage3_agent_scorecard/summary.json": {
            "stage3_agent_scorecard_complete": True,
            "evidence_paths": {"agent_lane": "artifacts/eval_agent/metrics.json"},
            "required_replay_ids": ["direct_rag"],
            "metrics": {
                "agent_lane_complete": 1.0,
                "routing_accuracy": 1.0,
                "tool_accuracy": 1.0,
                "rewrite_recovery": 1.0,
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
            },
            "thresholds": {
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
            },
            "failed": [],
        },
        "artifacts/reliability_security/summary.json": {
            "security_reliability_complete": True,
            "redteam_suite_path": "artifacts/reliability_security/redteam.jsonl",
            "reliability_suite_path": "artifacts/reliability_security/reliability.jsonl",
            "metrics": {
                "redteam_case_count": 20,
                "prompt_injection_block_recall": 1.0,
                "secrets_pii_leak_count": 0,
                "fallback_recovery_pass": 1.0,
                "deterministic_replay_pass": 1.0,
            },
            "thresholds": {
                "redteam_case_count": 20,
                "prompt_injection_block_recall": 1.0,
                "secrets_pii_leak_count": 0,
                "fallback_recovery_pass": 1.0,
                "deterministic_replay_pass": 1.0,
            },
            "failed": [],
        },
        "artifacts/stage4_ops_risk_scorecard/summary.json": {
            "stage4_ops_risk_scorecard_complete": True,
            "evidence_paths": {"observability": "artifacts/observability/summary.json"},
            "metrics": {
                "observability_complete": 1.0,
                "trace_export_present": 1.0,
                "latency_p50_ms_recorded": 1.0,
                "latency_p95_ms_recorded": 1.0,
                "token_cost_recorded": 1.0,
                "tool_success_rate_recorded": 1.0,
                "failed_run_analysis_count": 5,
                "service_ops_complete": 1.0,
                "healthz_pass": 1.0,
                "answer_pass": 1.0,
                "stream_pass": 1.0,
                "gates_pass": 1.0,
                "ops_summary_pass": 1.0,
                "path_safety_pass": 1.0,
                "security_redteam_complete": 1.0,
                "block_recall": 1.0,
                "secret_pii_leak_count": 0,
                "raw_persistence_count": 0,
                "tool_policy_violation_count": 0,
                "security_reliability_complete": 1.0,
                "redteam_case_count": 20,
                "prompt_injection_block_recall": 1.0,
                "secrets_pii_leak_count": 0,
                "fallback_recovery_pass": 1.0,
                "deterministic_replay_pass": 1.0,
                "cost_budget_complete": 1.0,
                "token_record_coverage": 1.0,
                "cost_record_coverage": 1.0,
                "budget_violation_count": 0,
                "dependency_security_complete": 1.0,
                "unresolved_unaccepted_alert_count": 0,
                "deployment_readiness_complete": 1.0,
                "public_exposure_requires_approval": 1.0,
                "rate_limit_plan_documented": 1.0,
                "secret_handling_documented": 1.0,
            },
            "thresholds": {
                "observability_complete": 1.0,
                "trace_export_present": 1.0,
                "latency_p50_ms_recorded": 1.0,
                "latency_p95_ms_recorded": 1.0,
                "token_cost_recorded": 1.0,
                "tool_success_rate_recorded": 1.0,
                "failed_run_analysis_count": 5,
                "service_ops_complete": 1.0,
                "healthz_pass": 1.0,
                "answer_pass": 1.0,
                "stream_pass": 1.0,
                "gates_pass": 1.0,
                "ops_summary_pass": 1.0,
                "path_safety_pass": 1.0,
                "security_redteam_complete": 1.0,
                "block_recall": 1.0,
                "secret_pii_leak_count": 0,
                "raw_persistence_count": 0,
                "tool_policy_violation_count": 0,
                "security_reliability_complete": 1.0,
                "redteam_case_count": 20,
                "prompt_injection_block_recall": 1.0,
                "secrets_pii_leak_count": 0,
                "fallback_recovery_pass": 1.0,
                "deterministic_replay_pass": 1.0,
                "cost_budget_complete": 1.0,
                "token_record_coverage": 1.0,
                "cost_record_coverage": 1.0,
                "budget_violation_count": 0,
                "dependency_security_complete": 1.0,
                "unresolved_unaccepted_alert_count": 0,
                "deployment_readiness_complete": 1.0,
                "public_exposure_requires_approval": 1.0,
                "rate_limit_plan_documented": 1.0,
                "secret_handling_documented": 1.0,
            },
            "failed": [],
        },
        "artifacts/deployment_readiness/summary.json": {
            "deployment_readiness_complete": True,
            "deployment_mode": "readiness_plan_no_public_exposure",
            "hosted_deployment_plan_path": "docs/portfolio/hosted-deployment-plan.md",
            "public_deployment_decision": "requires_explicit_owner_approval",
            "auth_boundary": "signed reviewer token",
            "rate_limit_boundary": "per-token request rate",
            "secret_handling_boundary": "secret manager only",
            "metrics": {
                "auth_boundary_documented": 1.0,
                "rate_limit_plan_documented": 1.0,
                "secret_handling_documented": 1.0,
                "public_exposure_requires_approval": 1.0,
                "one_command_fallback_documented": 1.0,
            },
            "thresholds": {
                "auth_boundary_documented": 1.0,
                "rate_limit_plan_documented": 1.0,
                "secret_handling_documented": 1.0,
                "public_exposure_requires_approval": 1.0,
                "one_command_fallback_documented": 1.0,
            },
            "failed": [],
        },
        "artifacts/interview_demo_package/summary.json": {
            "interview_demo_package_complete": True,
            "storyboard_path": "docs/portfolio/demo-storyboard.md",
            "generated_artifact_paths": [
                "docs/evidence/demo-package/01-entrypoint.md",
                "docs/evidence/demo-package/02-answer-citations.md",
                "docs/evidence/demo-package/03-trace-failure-cost.md",
                "docs/evidence/demo-package/04-security-boundaries.md",
            ],
            "reviewer_time_budget_minutes": 10,
            "demo_duration_minutes": 3,
            "metrics": {
                "three_minute_storyboard_present": 1.0,
                "generated_artifact_count": 4.0,
                "one_command_path_documented": 1.0,
                "ten_minute_reviewer_path_documented": 1.0,
                "security_observability_evidence_mapped": 1.0,
            },
            "thresholds": {
                "three_minute_storyboard_present": 1.0,
                "generated_artifact_count": 4.0,
                "one_command_path_documented": 1.0,
                "ten_minute_reviewer_path_documented": 1.0,
                "security_observability_evidence_mapped": 1.0,
            },
            "failed": [],
        },
        "artifacts/security_alerts/summary.json": {
            "dependency_security_complete": True,
            "risk_register_path": "docs/security/dependency-risk-register.md",
            "remediated_alerts": [],
            "open_alerts": [],
            "residual_risk_approval": "accepted",
            "metrics": {
                "langchain_patched": 1.0,
                "diskcache_absent": 1.0,
                "unresolved_unaccepted_alert_count": 0,
            },
            "thresholds": {
                "langchain_patched": 1.0,
                "diskcache_absent": 1.0,
                "unresolved_unaccepted_alert_count": 0,
            },
            "failed": [],
        },
    }
    for rel, payload in top_tier_payloads.items():
        _write(root / rel, json.dumps(payload))


def test_collect_portfolio_readiness_accepts_required_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {"offline_rag": {"ok": True}}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["local_evidence_bundle_check"] is True
    assert report["portfolio_readiness_check"] is False
    assert report["failed"] == []
    assert "cloud_deployment" in report["deferred"]
    assert report["second_stage_readiness"]["complete"] is False
    assert "security_redteam" in report["second_stage_readiness"]["missing"]
    assert report["top_tier_readiness"]["complete"] is False
    assert "stage3_independent_holdout" in report["top_tier_readiness"]["missing"]


def test_collect_portfolio_readiness_requires_second_stage_for_top_level_ready(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)
    _write_complete_second_stage(tmp_path)

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {"offline_rag": {"ok": True}}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["local_evidence_bundle_check"] is True
    assert report["second_stage_readiness"]["complete"] is True
    assert report["stage2_contract_schema_enforced"] is True
    assert report["portfolio_readiness_check"] is True
    assert report["interview_readiness_check"] is False
    assert report["top_tier_readiness"]["complete"] is False


def test_collect_portfolio_readiness_reports_missing_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)
    (tmp_path / "Dockerfile").unlink()

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": False, "lanes": {}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["portfolio_readiness_check"] is False
    assert report["local_evidence_bundle_check"] is False
    failed = {item["id"] for item in report["failed"]}
    assert {"gate_status", "dockerfile"}.issubset(failed)


def test_collect_portfolio_readiness_requires_docker_build_in_ci(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)
    _write(tmp_path / ".github/workflows/ci.yml", 'uv run pytest -m "not real"\n')

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["portfolio_readiness_check"] is False
    assert report["local_evidence_bundle_check"] is False
    failed = {item["id"] for item in report["failed"]}
    assert "ci_docker_build" in failed


def test_collect_portfolio_readiness_requires_paid_lane_plan(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)
    (tmp_path / "artifacts/paid_lane_plan/summary.json").unlink()

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {}},
    )

    report = collect_portfolio_readiness(tmp_path)

    failed = {item["id"] for item in report["failed"]}
    assert "paid_lane_plan" in failed


def test_collect_portfolio_readiness_requires_stage1_reviewer_docs(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)
    (tmp_path / "docs/portfolio/senior-reviewer-pack.md").unlink()

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["portfolio_readiness_check"] is False
    assert report["local_evidence_bundle_check"] is False
    failed = {item["id"] for item in report["failed"]}
    assert "senior_reviewer_pack_path" in failed


def test_portfolio_check_cli_requires_interview_readiness(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)
    _write_complete_second_stage(tmp_path)
    out = tmp_path / "portfolio_readiness.json"

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {}},
    )

    rc = main(["--root", str(tmp_path), "--out", str(out)])

    assert rc == 1
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["portfolio_readiness_check"] is True
    assert saved["interview_readiness_check"] is False
    assert saved["local_evidence_bundle_check"] is True
    assert saved["stage2_contract_schema_enforced"] is True
    assert saved["top_tier_readiness"]["complete"] is False


def test_top_tier_readiness_tracks_next_portfolio_level(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)
    _write_complete_second_stage(tmp_path)
    _write_complete_top_tier(tmp_path)

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["portfolio_readiness_check"] is True
    assert report["interview_readiness_check"] is True
    assert report["top_tier_readiness"]["complete"] is True
    assert report["top_tier_readiness"]["missing"] == []
    assert report["top_tier_readiness"]["failed"] == []


def test_top_tier_readiness_rejects_shallow_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)
    _write_complete_second_stage(tmp_path)
    _write(
        tmp_path / "docs/portfolio/top-tier-roadmap.md", "Stage 3 independent holdout\n"
    )
    _write(
        tmp_path / "artifacts/eval_stage3_holdout/metrics.json",
        json.dumps(
            {
                "stage3_holdout_quality_complete": True,
                "metrics": {"query_count": 10},
                "thresholds": {"query_count": 100},
                "failed": [],
            }
        ),
    )

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["portfolio_readiness_check"] is True
    assert report["interview_readiness_check"] is False
    assert report["top_tier_readiness"]["complete"] is False
    assert "top_tier_roadmap" in report["top_tier_readiness"]["failed"]
    assert "stage3_independent_holdout" in report["top_tier_readiness"]["failed"]
    details = {item["id"]: item for item in report["top_tier_readiness"]["details"]}
    assert (
        "term:Hosted or one-command reviewer demo"
        in details["top_tier_roadmap"]["issues"]
    )
    assert "query_count" in details["stage3_independent_holdout"]["issues"]


def test_portfolio_check_reports_second_stage_separately(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)
    _write(
        tmp_path / "artifacts/security_redteam/summary.json",
        json.dumps(
            {
                "security_redteam_complete": False,
                "failed": ["secrets_block_recall"],
            }
        ),
    )

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["local_evidence_bundle_check"] is True
    assert report["portfolio_readiness_check"] is False
    assert report["second_stage_readiness"]["complete"] is False
    assert "security_redteam" in report["second_stage_readiness"]["present"]
    assert "security_redteam" in report["second_stage_readiness"]["failed"]


def test_second_stage_readiness_rejects_bool_only_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)
    stage2_flags = {
        "artifacts/eval_stage2/coverage.json": {"eval_set_audit_complete": True},
        "artifacts/eval_stage2_real/metrics.json": {"holdout_quality_complete": True},
        "artifacts/eval_agent_stress/metrics.json": {"agent_stress_complete": True},
        "artifacts/retrieval_bakeoff/summary.json": {
            "retrieval_bakeoff_complete": True
        },
        "artifacts/visual_quality/summary.json": {"visual_quality_complete": True},
        "artifacts/service_ops/summary.json": {"service_ops_complete": True},
        "artifacts/security_redteam/summary.json": {"security_redteam_complete": True},
        "artifacts/cost_budget/summary.json": {"cost_budget_complete": True},
    }
    for rel, payload in stage2_flags.items():
        _write(tmp_path / rel, json.dumps(payload))

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["local_evidence_bundle_check"] is True
    assert report["portfolio_readiness_check"] is False
    assert report["second_stage_readiness"]["complete"] is False
    assert "eval_stage2_real" in report["second_stage_readiness"]["failed"]
    details = {item["id"]: item for item in report["second_stage_readiness"]["details"]}
    assert "eval_set_hash" in details["eval_stage2_real"]["issues"]
    assert "generation_model_id" in details["eval_stage2_real"]["issues"]


def test_second_stage_readiness_rejects_shallow_contract_payloads(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)
    eval_set_hash = "stage2-eval-set-v1"
    shallow_payloads = {
        "artifacts/eval_stage2/coverage.json": {
            "eval_set_audit_complete": True,
            "eval_set_hash": eval_set_hash,
            "metrics": {},
            "thresholds": {},
            "failed": [],
        },
        "artifacts/eval_stage2_real/metrics.json": {
            "holdout_quality_complete": True,
            "eval_set_hash": eval_set_hash,
            "thresholds_met": True,
            "per_slice_failed": [],
            "generation_model_id": "gpt-test",
            "judge_model_id": "judge-test",
            "embedding_model_id": "embed-test",
            "prompt_template_hash": "a" * 64,
            "metrics": {},
            "thresholds": {},
            "failed": [],
        },
        "artifacts/eval_agent_stress/metrics.json": {
            "agent_stress_complete": True,
            "metrics": {},
            "thresholds": {},
            "failed": [],
        },
        "artifacts/retrieval_bakeoff/summary.json": {
            "retrieval_bakeoff_complete": True,
            "decision": "keep_vector_until_reranker_wins",
            "metrics": {},
            "thresholds": {},
            "failed": [],
        },
        "artifacts/visual_quality/summary.json": {
            "visual_quality_complete": True,
            "metrics": {},
            "thresholds": {},
            "failed": [],
        },
        "artifacts/service_ops/summary.json": {
            "service_ops_complete": True,
            "full_answer_smoke": True,
            "full_gates_smoke": True,
            "metrics": {},
            "thresholds": {},
            "failed": [],
        },
        "artifacts/security_redteam/summary.json": {
            "security_redteam_complete": True,
            "metrics": {},
            "thresholds": {},
            "failed": [],
        },
        "artifacts/cost_budget/summary.json": {
            "cost_budget_complete": True,
            "metrics": {},
            "thresholds": {},
            "failed": [],
        },
    }
    for rel, payload in shallow_payloads.items():
        _write(tmp_path / rel, json.dumps(payload))

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["portfolio_readiness_check"] is False
    assert report["stage2_contract_schema_enforced"] is False
    assert set(report["second_stage_readiness"]["failed"]) == {
        "eval_stage2_coverage",
        "eval_stage2_real",
        "agent_stress",
        "retrieval_bakeoff",
        "visual_quality",
        "service_ops",
        "security_redteam",
        "cost_budget",
    }
    details = {item["id"]: item for item in report["second_stage_readiness"]["details"]}
    assert "query_count" in details["eval_stage2_coverage"]["issues"]
    assert "trajectory_pass_rate" in details["agent_stress"]["issues"]
    assert "healthz_pass" in details["service_ops"]["issues"]
    assert "secret_pii_leak_count" in details["security_redteam"]["issues"]
