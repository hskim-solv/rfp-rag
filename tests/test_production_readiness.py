from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.production_readiness import (
    evaluate_production_readiness,
    evaluate_dependency_security,
    evaluate_deployment_readiness,
    evaluate_interview_demo_package,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_deployment_contract_files(root: Path) -> None:
    _write(
        root / "Dockerfile",
        "FROM python:3.13-slim\nUSER appuser\nHEALTHCHECK CMD true\n${PORT:-8000}\n",
    )
    _write(
        root / "render.yaml",
        "\n".join(
            [
                "services:",
                "  - type: web",
                "    name: rfp-rag-reviewer-demo",
                "    runtime: docker",
                "    dockerfilePath: ./Dockerfile",
                "    plan: free",
                "    healthCheckPath: /healthz",
                "    envVars:",
                "      - key: RFP_RAG_PUBLIC_DEMO_MODE",
                '        value: "1"',
                "      - key: RFP_RAG_RATE_LIMIT_PER_MINUTE",
                '        value: "20"',
                "      - key: RFP_RAG_GIT_SHA",
                "        sync: false",
                "      - key: RFP_RAG_REVIEWER_TOKEN",
                "        sync: false",
                "",
            ]
        ),
    )
    _write(
        root / ".github/workflows/ci.yml",
        "jobs:\n  docker-build:\n    steps:\n      - name: Run service health smoke\n        run: curl /healthz && curl /v1/answer\n",
    )
    _write(
        root / "rfp_rag/service/app.py",
        (
            'description="local-reviewer hosted reviewer profile"\n'
            'os.getenv("RFP_RAG_PUBLIC_DEMO_MODE")\n'
            'os.getenv("RFP_RAG_REVIEWER_TOKEN")\n'
            'os.getenv("RFP_RAG_RATE_LIMIT_PER_MINUTE")\n'
            'os.getenv("RFP_RAG_GIT_SHA")\n'
            '_sse_event("error", {"code": "x"})\n'
        ),
    )
    _write(
        root / "rfp_rag/hosted_demo_smoke.py",
        "def run_hosted_demo_smoke(): pass\n",
    )
    _write(
        root / "artifacts/hosted_demo_smoke/summary.json",
        json.dumps(
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
                    "expected_git_sha_present": 1.0,
                    "revision_match_pass": 1.0,
                },
                "failed": [],
            }
        ),
    )
    _write(
        root / "artifacts/hosted_deployment_evidence/summary.json",
        json.dumps(
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
                "failed": [],
            }
        ),
    )


def test_evaluate_deployment_readiness_writes_hosted_plan(tmp_path: Path) -> None:
    _write_deployment_contract_files(tmp_path)

    summary = evaluate_deployment_readiness(root=tmp_path)

    assert summary["deployment_readiness_complete"] is True
    assert summary["metrics"]["auth_boundary_documented"] == 1.0
    assert summary["metrics"]["rate_limit_plan_documented"] == 1.0
    assert summary["metrics"]["secret_handling_documented"] == 1.0
    assert summary["metrics"]["docker_non_root_user"] == 1.0
    assert summary["metrics"]["docker_healthcheck"] == 1.0
    assert summary["metrics"]["ci_answer_contract_smoke"] == 1.0
    assert summary["metrics"]["sse_error_event_contract"] == 1.0
    assert summary["metrics"]["hosted_profile_env_contract"] == 1.0
    assert summary["metrics"]["hosted_demo_smoke_pass"] == 1.0
    assert summary["metrics"]["render_blueprint_contract"] == 1.0
    assert summary["metrics"]["hosted_deployment_evidence_pass"] == 1.0
    assert summary["thresholds"]["hosted_deployment_evidence_pass"] == 1.0
    assert (tmp_path / "docs/portfolio/hosted-deployment-plan.md").is_file()


def test_deployment_readiness_requires_hosted_deployment_evidence(
    tmp_path: Path,
) -> None:
    _write_deployment_contract_files(tmp_path)
    (tmp_path / "artifacts/hosted_deployment_evidence/summary.json").unlink()

    summary = evaluate_deployment_readiness(root=tmp_path)

    assert summary["deployment_readiness_complete"] is False
    assert summary["metrics"]["hosted_deployment_evidence_pass"] == 0.0
    assert "hosted_deployment_evidence_pass" in summary["failed"]


def test_deployment_readiness_fails_closed_without_runtime_contracts(
    tmp_path: Path,
) -> None:
    summary = evaluate_deployment_readiness(root=tmp_path)

    assert summary["deployment_readiness_complete"] is False
    assert "docker_non_root_user" in summary["failed"]
    assert "ci_answer_contract_smoke" in summary["failed"]


def test_evaluate_interview_demo_package_writes_storyboard_and_artifacts(
    tmp_path: Path,
) -> None:
    summary = evaluate_interview_demo_package(root=tmp_path)

    assert summary["interview_demo_package_complete"] is True
    assert summary["metrics"]["generated_artifact_count"] == 4.0
    assert (tmp_path / "docs/portfolio/demo-storyboard.md").is_file()
    for rel in summary["generated_artifact_paths"]:
        assert (tmp_path / rel).is_file()


def test_dependency_security_fails_closed_on_unaccepted_ragas_alert(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "uv.lock",
        "\n".join(
            [
                'name = "langchain"',
                'version = "1.3.9"',
                'name = "ragas"',
                'version = "0.4.3"',
                "",
            ]
        ),
    )

    summary = evaluate_dependency_security(root=tmp_path)

    assert summary["dependency_security_complete"] is False
    assert summary["metrics"]["langchain_patched"] == 1.0
    assert summary["metrics"]["diskcache_absent"] == 1.0
    assert summary["metrics"]["unresolved_unaccepted_alert_count"] == 1
    assert "unresolved_unaccepted_alert_count" in summary["failed"]
    risk = (tmp_path / "docs/security/dependency-risk-register.md").read_text(
        encoding="utf-8"
    )
    assert "accepted_by: PENDING" in risk


def test_dependency_security_accepts_documented_owner_risk(tmp_path: Path) -> None:
    _write(
        tmp_path / "uv.lock",
        "\n".join(
            [
                'name = "langchain"',
                'version = "1.3.9"',
                'name = "ragas"',
                'version = "0.4.3"',
                "",
            ]
        ),
    )
    _write(
        tmp_path / "docs/security/dependency-risk-register.md",
        """# Dependency Security Register

- `ragas` GHSA-95ww-475f-pr4f: accepted until judge migration.

accepted_by: user
accepted_scope: portfolio-local real-eval judge only
""",
    )

    summary = evaluate_dependency_security(root=tmp_path)

    assert summary["dependency_security_complete"] is True
    assert summary["residual_risk_approval"] == "accepted"
    saved = json.loads(
        (tmp_path / "artifacts/security_alerts/summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved == summary


def test_dependency_security_passes_when_vulnerable_packages_are_absent(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "uv.lock", 'name = "langchain-core"\nversion = "1.4.6"\n')

    summary = evaluate_dependency_security(root=tmp_path)

    assert summary["dependency_security_complete"] is True
    assert summary["metrics"]["langchain_patched"] == 1.0
    assert summary["metrics"]["diskcache_absent"] == 1.0
    assert summary["metrics"]["unresolved_unaccepted_alert_count"] == 0


def test_evaluate_production_readiness_writes_top_level_artifact(
    tmp_path: Path,
) -> None:
    _write_deployment_contract_files(tmp_path)
    _write(tmp_path / "uv.lock", 'name = "langchain-core"\nversion = "1.4.6"\n')

    summary = evaluate_production_readiness(root=tmp_path)

    assert summary["production_facing_readiness_complete"] is True
    assert summary["failed"] == []
    saved = json.loads(
        (tmp_path / "artifacts/production_readiness/summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved == summary
