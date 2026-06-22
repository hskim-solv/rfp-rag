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

    job = workflow["jobs"]["hosted-demo-smoke"]
    assert job["runs-on"] == "ubuntu-latest"
    steps = job["steps"]
    run_script = "\n".join(str(step.get("run", "")) for step in steps)
    assert "secrets.RFP_RAG_REVIEWER_TOKEN" in str(steps)
    assert "rfp_rag.hosted_demo_smoke" in run_script
    assert "rfp_rag.hosted_ops_summary" in run_script
    assert "rfp_rag.hosted_deployment_evidence" in run_script
    assert "actions/upload-artifact" in str(steps)
    assert "artifacts/hosted_deployment_evidence/summary.json" in str(steps)


def test_hosted_smoke_workflow_does_not_accept_token_as_input() -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/hosted-demo-smoke.yml").read_text(encoding="utf-8")
    )

    inputs = workflow[True]["workflow_dispatch"]["inputs"]
    assert "reviewer_token" not in inputs
