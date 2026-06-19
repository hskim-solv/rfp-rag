from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.production_readiness import (
    evaluate_dependency_security,
    evaluate_deployment_readiness,
    evaluate_interview_demo_package,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_evaluate_deployment_readiness_writes_hosted_plan(tmp_path: Path) -> None:
    summary = evaluate_deployment_readiness(root=tmp_path)

    assert summary["deployment_readiness_complete"] is True
    assert summary["metrics"]["auth_boundary_documented"] == 1.0
    assert summary["metrics"]["rate_limit_plan_documented"] == 1.0
    assert summary["metrics"]["secret_handling_documented"] == 1.0
    assert (tmp_path / "docs/portfolio/hosted-deployment-plan.md").is_file()


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
