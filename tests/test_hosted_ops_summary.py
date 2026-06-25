from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.hosted_ops_summary import build_hosted_ops_summary, main


def test_build_hosted_ops_summary_writes_redacted_render_evidence(
    tmp_path: Path,
) -> None:
    out = tmp_path / "artifacts/hosted_ops/summary.json"

    summary = build_hosted_ops_summary(
        service_url="https://rfp-rag-reviewer-demo.onrender.com",
        deployed_git_sha="250b9f9",
        out=out,
        confirm_logs_redacted=True,
        confirm_metrics_visible=True,
        confirm_rollback_runbook=True,
    )

    assert summary == {
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
            "last_known_good_git_sha": "250b9f9",
        },
    }
    assert json.loads(out.read_text(encoding="utf-8")) == summary


def test_hosted_ops_summary_cli_rejects_non_https_url(tmp_path: Path) -> None:
    out = tmp_path / "summary.json"

    rc = main(
        [
            "--service-url",
            "http://127.0.0.1:8017",
            "--deployed-git-sha",
            "250b9f9",
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()


def test_hosted_ops_summary_cli_requires_manual_evidence_confirmations(
    tmp_path: Path,
) -> None:
    out = tmp_path / "summary.json"

    rc = main(
        [
            "--service-url",
            "https://rfp-rag-reviewer-demo.onrender.com",
            "--deployed-git-sha",
            "250b9f9",
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()


def test_build_hosted_ops_summary_supports_hugging_face_spaces_provider(
    tmp_path: Path,
) -> None:
    out = tmp_path / "artifacts/hosted_ops/summary.json"

    summary = build_hosted_ops_summary(
        service_url="https://hskim-solv-rfp-rag-reviewer-demo.hf.space",
        deployed_git_sha="250b9f9",
        out=out,
        provider="huggingface_spaces",
        confirm_logs_redacted=True,
        confirm_metrics_visible=True,
        confirm_rollback_runbook=True,
    )

    assert summary["provider"] == "huggingface_spaces"
    assert summary["logs_evidence"]["source"] == "huggingface spaces logs"
    assert summary["metrics_evidence"]["source"] == "huggingface spaces runtime metrics"
