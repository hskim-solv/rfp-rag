from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from rfp_rag.business_readiness import (
    evaluate_business_readiness,
    write_business_readiness,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def seed_complete_repo(root: Path) -> None:
    write_json(
        root / "artifacts/final_portfolio_scorecard/summary.json",
        {
            "final_portfolio_scorecard_complete": True,
            "failed": [],
            "score_total": 100,
            "thresholds": {"minimum": 90},
            "metrics": {"score_total": 100},
        },
    )
    write_json(
        root / "artifacts/hosted_demo_smoke/summary.json",
        {
            "hosted_demo_smoke_complete": True,
            "failed": [],
            "observed_git_sha": "abc1234",
            "metrics": {"rate_limit_boundary_pass": 1.0},
        },
    )
    write_json(
        root / "artifacts/fresh_clone_smoke/summary.json",
        {
            "fresh_clone_offline_smoke_complete": True,
            "failed": [],
            "offline_only": True,
            "git_sha": "abc1234-fresh",
            "checks": ["pytest -m 'not real'", "startup"],
            "metrics": {"pytest_not_real_pass": 1.0},
        },
    )
    write_json(
        root / "artifacts/production_readiness/summary.json",
        {
            "production_facing_readiness_complete": True,
            "failed": [],
            "components": {
                "deployment_readiness": {
                    "deployment_readiness_complete": True,
                    "failed": [],
                    "metrics": {"deployment_pass": 1.0},
                },
                "hosted_deployment_evidence": {
                    "hosted_deployment_evidence_complete": True,
                    "failed": [],
                    "metrics": {"hosted_deployment_pass": 1.0},
                },
                "interview_demo_package": {
                    "interview_demo_package_complete": True,
                    "failed": [],
                    "evidence": {"runbook_present": True},
                },
                "dependency_security": {
                    "dependency_security_complete": True,
                    "failed": [],
                    "metrics": {"security_scan_pass": 1.0},
                },
            },
        },
    )
    write_json(
        root / "artifacts/stage4_ops_risk_scorecard/summary.json",
        {
            "stage4_ops_risk_scorecard_complete": True,
            "failed": [],
            "metrics": {"redaction_scan_pass": 1.0},
            "thresholds": {"redaction_scan_pass": 1.0},
        },
    )
    write_text(
        root / "docs/portfolio/case-study.md",
        "\n".join(
            [
                "# Case Study: Source-First RAG Delivery",
                "## Outcome",
                "This document describes an Agentic RAG engagement with a source-first evidence model.",
                "The project demonstrates practical impact from source-first RAG delivery and strong hiring readiness.",
                "It includes measurable outcomes and reproducible evidence path across the pipeline.",
            ]
        ),
    )
    write_text(
        root / "docs/portfolio/company-fit-matrix.md",
        "\n".join(
            [
                "# Company Fit Matrix",
                "## Outcome Lens",
                "Role focus: Senior AI Agent Engineer.",
                "This matrix includes Senior AI Agent Engineer tracks with an Outcome Lens on leadership and systems.",
                "Cross-role outcomes are mapped to hiring interview evidence and engineering ownership.",
            ]
        ),
    )
    write_text(
        root / "docs/portfolio/senior-reviewer-pack.md",
        "\n".join(
            [
                "# Senior Reviewer Pack",
                "## Reviewer Path",
                "This reviewer package prioritizes evidence for interview readiness and deployment safety.",
                "A reviewer follows the evidence-first onboarding path and checks reproducibility and safety evidence.",
                "It includes operational evidence, safety checks, and direct call examples.",
            ]
        ),
    )
    write_text(
        root / "docs/portfolio/freelance-offer-pack.md",
        "\n".join(
            [
                "# Freelance Offer Pack",
                "## Offer Types",
                "Offer options include Document RAG Diagnostic, Internal RAG MVP, and Agentic Workflow Automation.",
                "Each option is scoped for delivery and signed-off with evidence and acceptance criteria.",
                "The package keeps scope explicit so delivery targets remain auditable.",
            ]
        ),
    )
    write_text(
        root / "docs/portfolio/startup-validation-plan.md",
        "\n".join(
            [
                "# Startup Validation Plan",
                "## Pilot Gate",
                "Pilot Gate: run discovery interviews, collect learning, and track non-trust signals.",
                "Full SaaS readiness: not yet.",
                "Decision gate is built around learning milestones and proof of interview demand.",
            ]
        ),
    )


def _run_cli(root: Path, out: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "rfp_rag.business_readiness",
            "--root",
            str(root),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    return result.returncode, payload


def test_evaluate_business_readiness_scores_complete_repo(tmp_path: Path) -> None:
    seed_complete_repo(tmp_path)

    summary = evaluate_business_readiness(tmp_path)

    assert summary["business_readiness_complete"] is True
    assert summary["checks"]["case_study_present"] is True
    assert summary["evidence"]["employment"]["case_study"] is True
    assert summary["evidence"]["employment"]["company_fit_matrix"] is True
    assert summary["employment_ready"] is True
    assert summary["freelance_ready"] is True
    assert summary["startup_discovery_ready"] is True
    assert summary["startup_saas_ready"] is False
    assert summary["scores"]["employment"] >= 90
    assert summary["scores"]["freelance"] >= 80
    assert summary["scores"]["startup_discovery"] >= 65
    assert "full_saas_production" in summary["non_claims"]
    assert summary["failed"] == []
    for category in summary["evidence"].values():
        assert all(isinstance(value, bool) for value in category.values())


def test_evaluate_business_readiness_fails_closed_without_freelance_pack(
    tmp_path: Path,
) -> None:
    seed_complete_repo(tmp_path)
    (tmp_path / "docs/portfolio/freelance-offer-pack.md").unlink()

    summary = evaluate_business_readiness(tmp_path)

    assert summary["business_readiness_complete"] is False
    assert summary["freelance_ready"] is False
    assert "freelance_offer_pack_present" in summary["failed"]
    assert summary["scores"]["freelance"] < 80


def test_evaluate_business_readiness_does_not_claim_saas_without_saas_evidence(
    tmp_path: Path,
) -> None:
    seed_complete_repo(tmp_path)

    summary = evaluate_business_readiness(tmp_path)

    assert summary["startup_saas_ready"] is False
    assert summary["evidence"]["startup"]["saas_production_evidence"] is False


def test_evaluate_business_readiness_fails_closed_without_stage4_ops_risk(
    tmp_path: Path,
) -> None:
    seed_complete_repo(tmp_path)
    (tmp_path / "artifacts/stage4_ops_risk_scorecard/summary.json").unlink()

    summary = evaluate_business_readiness(tmp_path)

    assert summary["business_readiness_complete"] is False
    assert summary["checks"]["ops_risk_scorecard_pass"] is False
    assert "ops_risk_scorecard_pass" in summary["failed"]


def test_write_business_readiness_accepts_positional_args(tmp_path: Path) -> None:
    seed_complete_repo(tmp_path)
    out = tmp_path / "out.json"

    summary = write_business_readiness(tmp_path, out)

    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == summary
    assert written["business_readiness_complete"] is True


def test_business_readiness_cli_succeeds_with_complete_repo(
    tmp_path: Path,
) -> None:
    seed_complete_repo(tmp_path)
    out = tmp_path / "artifacts" / "business_readiness" / "summary.json"

    returncode, payload = _run_cli(tmp_path, out)

    assert returncode == 0
    assert payload["business_readiness_complete"] is True
    assert out.is_file()


def test_business_readiness_cli_fails_without_freelance_pack(tmp_path: Path) -> None:
    seed_complete_repo(tmp_path)
    (tmp_path / "docs/portfolio/freelance-offer-pack.md").unlink()
    out = tmp_path / "artifacts" / "business_readiness" / "summary.json"

    returncode, payload = _run_cli(tmp_path, out)

    assert returncode == 1
    assert payload["business_readiness_complete"] is False


def test_shallow_case_study_fails_case_study_present(tmp_path: Path) -> None:
    seed_complete_repo(tmp_path)
    write_text(
        tmp_path / "docs/portfolio/case-study.md",
        "Agentic RAG source-first case.",
    )

    summary = evaluate_business_readiness(tmp_path)

    assert summary["checks"]["case_study_present"] is False
    assert "case_study_present" in summary["failed"]


def test_case_study_without_headings_still_fails(tmp_path: Path) -> None:
    seed_complete_repo(tmp_path)
    write_text(
        tmp_path / "docs/portfolio/case-study.md",
        " ".join(
            [
                "Agentic RAG source-first case study with plenty of text that clearly mentions",
                "source-first and Agentic RAG. This body is over one hundred twenty characters",
                "long but deliberately has no markdown heading marker even though it includes all",
                "required terms to validate structure enforcement.",
            ]
        ),
    )

    summary = evaluate_business_readiness(tmp_path)

    assert summary["checks"]["case_study_present"] is False
    assert "case_study_present" in summary["failed"]


def test_final_portfolio_scorecard_missing_failed_fails_closed(tmp_path: Path) -> None:
    seed_complete_repo(tmp_path)
    write_json(
        tmp_path / "artifacts/final_portfolio_scorecard/summary.json",
        {
            "final_portfolio_scorecard_complete": True,
            "score_total": 100,
            "thresholds": {"minimum": 90},
            "metrics": {"score_total": 100},
        },
    )
    summary = evaluate_business_readiness(tmp_path)

    assert summary["checks"]["final_portfolio_scorecard_pass"] is False
    assert "final_portfolio_scorecard_pass" in summary["failed"]
    assert summary["business_readiness_complete"] is False


def test_final_portfolio_scorecard_incomplete_fails_check(tmp_path: Path) -> None:
    seed_complete_repo(tmp_path)
    write_json(
        tmp_path / "artifacts/final_portfolio_scorecard/summary.json",
        {
            "final_portfolio_scorecard_complete": False,
            "failed": [],
            "score_total": 100,
            "thresholds": {"minimum": 90},
            "metrics": {"score_total": 100},
        },
    )

    summary = evaluate_business_readiness(tmp_path)

    assert summary["checks"]["final_portfolio_scorecard_pass"] is False
    assert "final_portfolio_scorecard_pass" in summary["failed"]
    assert summary["business_readiness_complete"] is False


def test_final_portfolio_scorecard_failed_entries_fail_closed(tmp_path: Path) -> None:
    seed_complete_repo(tmp_path)
    write_json(
        tmp_path / "artifacts/final_portfolio_scorecard/summary.json",
        {
            "final_portfolio_scorecard_complete": True,
            "failed": ["some_unresolved_issue"],
            "score_total": 100,
            "thresholds": {"minimum": 90},
            "metrics": {"score_total": 100},
        },
    )

    summary = evaluate_business_readiness(tmp_path)

    assert summary["checks"]["final_portfolio_scorecard_pass"] is False
    assert "final_portfolio_scorecard_pass" in summary["failed"]
    assert summary["business_readiness_complete"] is False


def test_stage4_ops_risk_shallow_payload_fails_check(tmp_path: Path) -> None:
    seed_complete_repo(tmp_path)
    write_json(
        tmp_path / "artifacts/stage4_ops_risk_scorecard/summary.json", {"failed": []}
    )

    summary = evaluate_business_readiness(tmp_path)

    assert summary["checks"]["ops_risk_scorecard_pass"] is False
    assert "ops_risk_scorecard_pass" in summary["failed"]
    assert summary["business_readiness_complete"] is False


def test_shallow_hosted_demo_smoke_fails_hosted_check(tmp_path: Path) -> None:
    seed_complete_repo(tmp_path)
    write_json(
        tmp_path / "artifacts/hosted_demo_smoke/summary.json",
        {"hosted_demo_smoke_complete": True, "failed": []},
    )

    summary = evaluate_business_readiness(tmp_path)

    assert summary["checks"]["hosted_demo_smoke_pass"] is False
    assert "hosted_demo_smoke_pass" in summary["failed"]
    assert summary["business_readiness_complete"] is False


def test_shallow_fresh_clone_smoke_fails_fresh_clone_check(tmp_path: Path) -> None:
    seed_complete_repo(tmp_path)
    write_json(
        tmp_path / "artifacts/fresh_clone_smoke/summary.json",
        {
            "fresh_clone_offline_smoke_complete": True,
            "failed": [],
            "offline_only": True,
            "git_sha": "abc1234-fresh",
        },
    )

    summary = evaluate_business_readiness(tmp_path)

    assert summary["checks"]["fresh_clone_smoke_pass"] is False
    assert "fresh_clone_smoke_pass" in summary["failed"]
    assert summary["business_readiness_complete"] is False


def test_shallow_production_readiness_fails_production_check(tmp_path: Path) -> None:
    seed_complete_repo(tmp_path)
    write_json(
        tmp_path / "artifacts/production_readiness/summary.json",
        {"production_facing_readiness_complete": True, "failed": []},
    )

    summary = evaluate_business_readiness(tmp_path)

    assert summary["checks"]["production_readiness_pass"] is False
    assert "production_readiness_pass" in summary["failed"]
    assert summary["business_readiness_complete"] is False


def test_production_readiness_incomplete_component_complete_flag_fails(
    tmp_path: Path,
) -> None:
    seed_complete_repo(tmp_path)
    write_json(
        tmp_path / "artifacts/production_readiness/summary.json",
        {
            "production_facing_readiness_complete": True,
            "failed": [],
            "components": {
                "deployment_readiness": {
                    "deployment_readiness_complete": False,
                    "failed": [],
                    "metrics": {"deployment_pass": 1.0},
                },
                "hosted_deployment_evidence": {
                    "hosted_deployment_evidence_complete": True,
                    "failed": [],
                    "metrics": {"hosted_deployment_pass": 1.0},
                },
                "interview_demo_package": {
                    "interview_demo_package_complete": True,
                    "failed": [],
                    "evidence": {"runbook_present": True},
                },
                "dependency_security": {
                    "dependency_security_complete": True,
                    "failed": [],
                    "metrics": {"security_scan_pass": 1.0},
                },
            },
        },
    )

    summary = evaluate_business_readiness(tmp_path)

    assert summary["checks"]["production_readiness_pass"] is False
    assert "production_readiness_pass" in summary["failed"]
    assert summary["business_readiness_complete"] is False


def test_production_readiness_dependency_security_incomplete_fails(
    tmp_path: Path,
) -> None:
    seed_complete_repo(tmp_path)
    write_json(
        tmp_path / "artifacts/production_readiness/summary.json",
        {
            "production_facing_readiness_complete": True,
            "failed": [],
            "components": {
                "deployment_readiness": {
                    "deployment_readiness_complete": True,
                    "failed": [],
                    "metrics": {"deployment_pass": 1.0},
                },
                "hosted_deployment_evidence": {
                    "hosted_deployment_evidence_complete": True,
                    "failed": [],
                    "metrics": {"hosted_deployment_pass": 1.0},
                },
                "interview_demo_package": {
                    "interview_demo_package_complete": True,
                    "failed": [],
                    "evidence": {"runbook_present": True},
                },
                "dependency_security": {
                    "dependency_security_complete": False,
                    "failed": [],
                    "metrics": {"security_scan_pass": 1.0},
                },
            },
        },
    )

    summary = evaluate_business_readiness(tmp_path)

    assert summary["checks"]["production_readiness_pass"] is False
    assert "production_readiness_pass" in summary["failed"]
    assert summary["business_readiness_complete"] is False


def test_production_readiness_dependency_security_failed_entries_fails(
    tmp_path: Path,
) -> None:
    seed_complete_repo(tmp_path)
    write_json(
        tmp_path / "artifacts/production_readiness/summary.json",
        {
            "production_facing_readiness_complete": True,
            "failed": [],
            "components": {
                "deployment_readiness": {
                    "deployment_readiness_complete": True,
                    "failed": [],
                    "metrics": {"deployment_pass": 1.0},
                },
                "hosted_deployment_evidence": {
                    "hosted_deployment_evidence_complete": True,
                    "failed": [],
                    "metrics": {"hosted_deployment_pass": 1.0},
                },
                "interview_demo_package": {
                    "interview_demo_package_complete": True,
                    "failed": [],
                    "evidence": {"runbook_present": True},
                },
                "dependency_security": {
                    "dependency_security_complete": True,
                    "failed": ["open_alerts"],
                    "metrics": {"security_scan_pass": 1.0},
                },
            },
        },
    )

    summary = evaluate_business_readiness(tmp_path)

    assert summary["checks"]["production_readiness_pass"] is False
    assert "production_readiness_pass" in summary["failed"]
    assert summary["business_readiness_complete"] is False
