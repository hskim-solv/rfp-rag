from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.stage4_ops_risk_scorecard import (
    build_stage4_ops_risk_scorecard,
    main,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_complete_inputs(root: Path) -> None:
    _write_json(
        root / "artifacts/observability/summary.json",
        {
            "observability_complete": True,
            "metrics": {
                "trace_export_present": 1.0,
                "latency_p50_ms_recorded": 1.0,
                "latency_p95_ms_recorded": 1.0,
                "token_cost_recorded": 1.0,
                "tool_success_rate_recorded": 1.0,
                "failed_run_analysis_count": 5,
            },
            "failed": [],
        },
    )
    _write_json(
        root / "artifacts/service_ops/summary.json",
        {
            "service_ops_complete": True,
            "metrics": {
                "healthz_pass": 1.0,
                "answer_pass": 1.0,
                "stream_pass": 1.0,
                "gates_pass": 1.0,
                "ops_summary_pass": 1.0,
                "path_safety_pass": 1.0,
                "token_cost_distribution_recorded": 1.0,
            },
            "failed": [],
        },
    )
    _write_json(
        root / "artifacts/security_redteam/summary.json",
        {
            "security_redteam_complete": True,
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
            "failed": [],
        },
    )
    _write_json(
        root / "artifacts/reliability_security/summary.json",
        {
            "security_reliability_complete": True,
            "metrics": {
                "redteam_case_count": 20,
                "prompt_injection_block_recall": 1.0,
                "secrets_pii_leak_count": 0,
                "fallback_recovery_pass": 1.0,
                "deterministic_replay_pass": 1.0,
            },
            "failed": [],
        },
    )
    _write_json(
        root / "artifacts/cost_budget/summary.json",
        {
            "cost_budget_complete": True,
            "metrics": {
                "token_record_coverage": 1.0,
                "cost_record_coverage": 1.0,
                "budget_violation_count": 0,
            },
            "failed": [],
        },
    )
    _write_json(
        root / "artifacts/security_alerts/summary.json",
        {
            "dependency_security_complete": True,
            "metrics": {
                "langchain_patched": 1.0,
                "diskcache_absent": 1.0,
                "unresolved_unaccepted_alert_count": 0,
            },
            "failed": [],
        },
    )
    _write_json(
        root / "artifacts/deployment_readiness/summary.json",
        {
            "deployment_readiness_complete": True,
            "metrics": {
                "public_exposure_requires_approval": 1.0,
                "rate_limit_plan_documented": 1.0,
                "secret_handling_documented": 1.0,
                "sse_error_event_contract": 1.0,
            },
            "failed": [],
        },
    )


def test_build_stage4_ops_risk_scorecard_accepts_complete_evidence(
    tmp_path: Path,
) -> None:
    _write_complete_inputs(tmp_path)

    summary = build_stage4_ops_risk_scorecard(root=tmp_path)

    assert summary["stage4_ops_risk_scorecard_complete"] is True
    assert summary["failed"] == []
    assert summary["metrics"]["failed_run_analysis_count"] == 5
    assert summary["metrics"]["secret_pii_leak_count"] == 0


def test_build_stage4_ops_risk_scorecard_fails_on_secret_leak(
    tmp_path: Path,
) -> None:
    _write_complete_inputs(tmp_path)
    _write_json(
        tmp_path / "artifacts/security_redteam/summary.json",
        {
            "security_redteam_complete": True,
            "metrics": {
                "block_recall": 1.0,
                "malicious_document_pass": 1.0,
                "malicious_retrieved_evidence_pass": 1.0,
                "malicious_tool_output_pass": 1.0,
                "artifact_redaction_scan_pass": 1.0,
                "publishable_allowlist_pass": 1.0,
                "retention_scope_pass": 1.0,
                "secret_pii_leak_count": 1,
                "raw_persistence_count": 0,
                "tool_policy_violation_count": 0,
            },
            "failed": [],
        },
    )

    summary = build_stage4_ops_risk_scorecard(root=tmp_path)

    assert summary["stage4_ops_risk_scorecard_complete"] is False
    assert "secret_pii_leak_count" in summary["failed"]


def test_stage4_ops_risk_scorecard_cli_writes_summary(tmp_path: Path) -> None:
    _write_complete_inputs(tmp_path)
    out = tmp_path / "out/summary.json"

    rc = main(["--root", str(tmp_path), "--out", str(out)])

    assert rc == 0
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["stage4_ops_risk_scorecard_complete"] is True
