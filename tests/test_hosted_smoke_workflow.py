from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_hosted_smoke_workflow_is_manual_and_secret_backed() -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/hosted-demo-smoke.yml").read_text(encoding="utf-8")
    )

    trigger = workflow[True]
    assert "workflow_dispatch" in trigger
    service_url = trigger["workflow_dispatch"]["inputs"]["service_url"]
    assert service_url["required"] is True
    assert service_url["type"] == "string"
    for name in (
        "confirm_logs_redacted",
        "confirm_metrics_visible",
        "confirm_rollback_runbook",
    ):
        assert trigger["workflow_dispatch"]["inputs"][name]["required"] is True
        assert trigger["workflow_dispatch"]["inputs"][name]["type"] == "boolean"

    job = workflow["jobs"]["hosted-demo-smoke"]
    assert job["runs-on"] == "ubuntu-latest"
    steps = job["steps"]
    run_script = "\n".join(str(step.get("run", "")) for step in steps)
    assert "secrets.RFP_RAG_REVIEWER_TOKEN" in str(steps)
    assert "rfp_rag.hosted_demo_smoke" in run_script
    assert "--expected-git-sha" in run_script
    assert "rfp_rag.hosted_ops_summary" in run_script
    assert "--confirm-logs-redacted" in run_script
    assert "--confirm-metrics-visible" in run_script
    assert "--confirm-rollback-runbook" in run_script
    assert "rfp_rag.hosted_deployment_evidence" in run_script
    assert "rfp_rag.production_readiness" in run_script
    assert "actions/upload-artifact" in str(steps)
    assert "artifacts/hosted_deployment_evidence/summary.json" in str(steps)
    assert "artifacts/production_readiness/summary.json" in str(steps)


def test_hosted_smoke_workflow_does_not_accept_token_as_input() -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/hosted-demo-smoke.yml").read_text(encoding="utf-8")
    )

    inputs = workflow[True]["workflow_dispatch"]["inputs"]
    assert "reviewer_token" not in inputs
