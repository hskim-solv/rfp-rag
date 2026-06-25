from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hosted_evidence_script_is_fail_closed_and_runs_full_gate_chain() -> None:
    script = (ROOT / "scripts/hosted-evidence.sh").read_text(encoding="utf-8")

    assert "SERVICE_URL must be the approved HTTPS hosted demo URL" in script
    assert "RFP_RAG_REVIEWER_TOKEN must be set" in script
    assert '[[ "$SERVICE_URL" != https://* ]]' in script
    assert '[[ "$CONFIRM_LOGS_REDACTED" != "true" ]]' in script
    assert '[[ "$CONFIRM_METRICS_VISIBLE" != "true" ]]' in script
    assert '[[ "$CONFIRM_ROLLBACK_RUNBOOK" != "true" ]]' in script
    assert "rfp_rag.hosted_demo_smoke" in script
    assert "rfp_rag.hosted_ops_summary" in script
    assert "rfp_rag.hosted_deployment_evidence" in script
    assert "rfp_rag.production_readiness" in script
    assert "rfp_rag.final_portfolio_scorecard" in script
    assert "rfp_rag.portfolio_check" in script
    assert "hosted_evidence_ok=true" in script
