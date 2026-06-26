from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.hosted_deployment_evidence import build_hosted_deployment_evidence


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_hosted_deployment_evidence_accepts_https_smoke_logs_and_metrics(
    tmp_path: Path,
) -> None:
    _write_json(
        tmp_path / "artifacts/hosted_demo_smoke/summary.json",
        {
            "hosted_demo_smoke_complete": True,
            "base_url": "https://rfp-rag-reviewer-demo.onrender.com",
            "reviewer_token_boundary": "required",
            "metrics": {
                "healthz_pass": 1.0,
                "reviewer_token_boundary_pass": 1.0,
                "gates_pass": 1.0,
                "answer_pass": 1.0,
                "stream_pass": 1.0,
                "public_safe_sources_pass": 1.0,
                "rate_limit_boundary_pass": 1.0,
                "expected_git_sha_present": 1.0,
                "revision_match_pass": 1.0,
            },
            "observed_status": {
                "healthz": 200,
                "unauth_answer": 401,
                "gates": 200,
                "answer": 200,
                "stream": 200,
            },
            "failed": [],
        },
    )
    _write_json(
        tmp_path / "artifacts/hosted_ops/summary.json",
        {
            "provider": "render",
            "service_url": "https://rfp-rag-reviewer-demo.onrender.com",
            "deployment_status": "live",
            "deploy_smoke_status": "SUCCESS",
            "logs_evidence": {
                "source": "render dashboard or render logs",
                "redacted": True,
                "healthz_2xx_seen": True,
                "answer_2xx_seen": True,
                "unauth_401_seen": True,
                "secret_leak_count": 0,
                "raw_rfp_text_seen": False,
            },
            "metrics_evidence": {
                "source": "render service metrics",
                "redacted": True,
                "http_request_count_visible": True,
                "latency_visible": True,
                "error_count_visible": True,
            },
            "rollback_evidence": {
                "runbook_path": "docs/portfolio/hosted-deployment-runbook.md",
                "rollback_procedure_documented": True,
                "last_known_good_git_sha": "fb0f615",
            },
        },
    )
    (tmp_path / "docs/portfolio/hosted-deployment-runbook.md").parent.mkdir(
        parents=True
    )
    (tmp_path / "docs/portfolio/hosted-deployment-runbook.md").write_text(
        "rollback procedure\nrotate reviewer token\n", encoding="utf-8"
    )

    summary = build_hosted_deployment_evidence(root=tmp_path)

    assert summary["hosted_deployment_evidence_complete"] is True
    assert summary["metrics"] == {
        "https_url_present": 1.0,
        "hosted_smoke_pass": 1.0,
        "deploy_smoke_success": 1.0,
        "logs_redacted_pass": 1.0,
        "metrics_visible_pass": 1.0,
        "rollback_runbook_pass": 1.0,
        "secret_leak_count": 0.0,
        "raw_rfp_text_seen": 0.0,
    }
    assert summary["failed"] == []


def test_hosted_deployment_evidence_fails_closed_without_https_url(
    tmp_path: Path,
) -> None:
    _write_json(
        tmp_path / "artifacts/hosted_demo_smoke/summary.json",
        {
            "hosted_demo_smoke_complete": True,
            "base_url": "http://127.0.0.1:8017",
            "metrics": {"healthz_pass": 1.0},
            "failed": [],
        },
    )

    summary = build_hosted_deployment_evidence(root=tmp_path)

    assert summary["hosted_deployment_evidence_complete"] is False
    assert "https_url_present" in summary["failed"]
    assert "deploy_smoke_success" in summary["failed"]
    assert "logs_redacted_pass" in summary["failed"]
    assert "metrics_visible_pass" in summary["failed"]
    assert "rollback_runbook_pass" in summary["failed"]
