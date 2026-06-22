from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.final_portfolio_scorecard import (
    build_final_portfolio_scorecard,
    main,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write(path, json.dumps(payload, ensure_ascii=False))


def _complete_root(root: Path) -> None:
    shared_story = (
        "public-safe hosted reviewer demo for an Agentic RAG backend with "
        "source-first Korean public RFP evidence and local/container "
        "reproducibility evidence. It does not claim hosted cloud production, "
        "live-traffic SLO, provider billing telemetry, or reranker quality win."
    )
    for rel in (
        "README.md",
        "docs/portfolio/senior-reviewer-pack.md",
        "docs/portfolio/company-fit-matrix.md",
        "docs/portfolio/korean-one-page-case-study.md",
        "docs/portfolio/demo-runbook.md",
        "docs/portfolio/resume-interview-bullets.md",
    ):
        _write(root / rel, shared_story)
    _write(
        root / ".github/workflows/ci.yml",
        'uv run pytest -m "not real"\ndocker build -t rfp-rag-service:ci .\n',
    )
    _write_json(
        root / "docs/portfolio/claim-manifest.json",
        {
            "schema_version": "senior-portfolio-claim-v1",
            "claim_level": "public_safe_hosted_reviewer_demo",
            "headline": "public-safe hosted reviewer demo for an Agentic RAG backend",
            "non_claims": {
                "hosted_cloud_production": False,
                "live_traffic_slo": False,
                "provider_billing_telemetry": False,
                "reranker_quality_win": False,
                "full_auth_rate_limit_session_operations": False,
            },
            "required_public_docs": [
                "README.md",
                "docs/portfolio/senior-reviewer-pack.md",
                "docs/portfolio/company-fit-matrix.md",
                "docs/portfolio/korean-one-page-case-study.md",
                "docs/portfolio/demo-runbook.md",
                "docs/portfolio/resume-interview-bullets.md",
            ],
        },
    )
    _write_json(
        root / "docs/portfolio/public-package-manifest.json",
        {
            "schema_version": "public-package-v1",
            "public_safe": True,
            "publishable_artifacts": [
                "README.md",
                "docs/portfolio/senior-reviewer-pack.md",
                "docs/portfolio/company-fit-matrix.md",
                "docs/portfolio/korean-one-page-case-study.md",
                "docs/portfolio/demo-runbook.md",
                "docs/portfolio/resume-interview-bullets.md",
            ],
            "excluded_from_public_package": [
                ".env",
                "data/files",
                "artifacts/parsed_docs",
                "artifacts/**/checkpoints.sqlite",
            ],
        },
    )
    _write_json(
        root / "artifacts/stage2_quality_scorecard/summary.json",
        {
            "stage2_quality_scorecard_complete": True,
            "metrics": {
                "parser_average_quality_score": 0.97,
                "context_precision_at5": 1.0,
                "context_recall_at5": 1.0,
                "citation_precision_proxy": 1.0,
                "stage3_answer_relevancy": 0.88,
            },
            "thresholds": {},
            "failed": [],
        },
    )
    _write_json(
        root / "artifacts/stage3_agent_scorecard/summary.json",
        {
            "stage3_agent_scorecard_complete": True,
            "metrics": {
                "trajectory_pass_rate": 1.0,
                "required_replay_coverage": 1.0,
                "hitl_approval_convergence": 1.0,
            },
            "thresholds": {},
            "failed": [],
        },
    )
    _write_json(
        root / "artifacts/stage4_ops_risk_scorecard/summary.json",
        {
            "stage4_ops_risk_scorecard_complete": True,
            "metrics": {
                "trace_export_present": 1.0,
                "secret_pii_leak_count": 0,
                "tool_policy_violation_count": 0,
                "unresolved_unaccepted_alert_count": 0,
                "public_exposure_requires_approval": 1.0,
            },
            "thresholds": {},
            "failed": [],
        },
    )
    _write_json(
        root / "artifacts/production_readiness/summary.json",
        {
            "production_facing_readiness_complete": True,
            "failed": [],
            "components": {
                "hosted_demo_smoke": {
                    "hosted_demo_smoke_complete": True,
                    "failed": [],
                }
            },
        },
    )
    _write_json(
        root / "artifacts/hosted_demo_smoke/summary.json",
        {
            "hosted_demo_smoke_complete": True,
            "base_url": "https://reviewer.example",
            "reviewer_token_boundary": "required",
            "metrics": {
                "healthz_pass": 1.0,
                "reviewer_token_boundary_pass": 1.0,
                "gates_pass": 1.0,
                "answer_pass": 1.0,
                "stream_pass": 1.0,
                "public_safe_sources_pass": 1.0,
            },
            "failed": [],
        },
    )
    _write_json(
        root / "artifacts/hosted_deployment_evidence/summary.json",
        {
            "hosted_deployment_evidence_complete": True,
            "service_url": "https://reviewer.example",
            "metrics": {
                "https_url_present": 1.0,
                "hosted_smoke_pass": 1.0,
                "deploy_smoke_success": 1.0,
                "logs_redacted_pass": 1.0,
                "metrics_visible_pass": 1.0,
                "rollback_runbook_pass": 1.0,
                "secret_leak_count": 0.0,
                "raw_rfp_text_seen": 0.0,
            },
            "thresholds": {},
            "failed": [],
        },
    )
    _write_json(
        root / "artifacts/fresh_clone_smoke/summary.json",
        {
            "fresh_clone_offline_smoke_complete": True,
            "offline_only": True,
            "metrics": {
                "git_clone_pass": 1.0,
                "uv_sync_pass": 1.0,
                "synthetic_corpus_pass": 1.0,
                "ruff_format_pass": 1.0,
                "ruff_lint_pass": 1.0,
                "pytest_not_real_pass": 1.0,
                "no_credentials_required": 1.0,
            },
            "thresholds": {},
            "failed": [],
        },
    )


def test_build_final_portfolio_scorecard_accepts_complete_stage5_evidence(
    tmp_path: Path,
) -> None:
    _complete_root(tmp_path)

    summary = build_final_portfolio_scorecard(root=tmp_path)

    assert summary["final_portfolio_scorecard_complete"] is True
    assert summary["score_total"] == 100
    assert summary["score_threshold"] == 90
    assert summary["claim_boundary"] == "public_safe_hosted_reviewer_demo"
    assert summary["failed"] == []
    assert summary["metrics"]["fresh_clone_offline_smoke_pass"] == 1.0
    assert summary["metrics"]["hosted_demo_smoke_pass"] == 1.0
    assert summary["metrics"]["hosted_deployment_evidence_pass"] == 1.0
    assert summary["metrics"]["docs_claim_consistency_pass"] == 1.0
    assert summary["metrics"]["public_package_redaction_pass"] == 1.0
    assert summary["dimensions"]["source_first_rag_quality"]["score"] == 20
    assert summary["dimensions"]["agentic_engineering_depth"]["score"] == 20


def test_build_final_portfolio_scorecard_rejects_unbounded_hosted_claim(
    tmp_path: Path,
) -> None:
    _complete_root(tmp_path)
    _write(
        tmp_path / "README.md",
        "This is a hosted production service with live-traffic SLO.",
    )

    summary = build_final_portfolio_scorecard(root=tmp_path)

    assert summary["final_portfolio_scorecard_complete"] is False
    assert "claim_boundary_pass" in summary["failed"]
    assert summary["metrics"]["hosted_cloud_claim"] == 1.0
    assert summary["metrics"]["live_traffic_slo_claim"] == 1.0


def test_build_final_portfolio_scorecard_rejects_missing_hosted_deployment_evidence(
    tmp_path: Path,
) -> None:
    _complete_root(tmp_path)
    (tmp_path / "artifacts/hosted_deployment_evidence/summary.json").unlink()

    summary = build_final_portfolio_scorecard(root=tmp_path)

    assert summary["final_portfolio_scorecard_complete"] is False
    assert "hosted_deployment_evidence_pass" in summary["failed"]
    assert "dimension:production_operations" in summary["failed"]


def test_final_portfolio_scorecard_cli_writes_summary(tmp_path: Path) -> None:
    _complete_root(tmp_path)
    out = tmp_path / "artifacts/final_portfolio_scorecard/summary.json"

    rc = main(["--root", str(tmp_path), "--out", str(out)])

    assert rc == 0
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["final_portfolio_scorecard_complete"] is True
    assert saved["score_total"] == 100
