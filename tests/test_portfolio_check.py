from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.portfolio_check import collect_portfolio_readiness, main


def _write(path: Path, text: str = "ok") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _minimal_ready_root(root: Path) -> None:
    _write(root / "README.md", "docs/architecture/system-architecture.md\n")
    _write(root / "REPORT.md", "Architecture evidence map\n")
    _write(root / "Dockerfile", "FROM python:3.13-slim\n")
    _write(root / ".github/workflows/ci.yml", 'uv run pytest -m "not real"\n')
    _write(
        root / "docs/architecture/system-architecture.md", "## Operational Boundaries\n"
    )
    _write(root / "docs/adr/0014-fastapi-service-surface.md")
    _write(root / "docs/adr/0015-docker-ci-baseline.md")
    _write(root / "docs/adr/0016-mcp-style-ops-tool-server.md")
    _write(
        root / "artifacts/guardrails/summary.json",
        json.dumps(
            {
                "guardrail_regression_complete": True,
                "case_count": 7,
                "passed": 7,
                "failed": 0,
                "metrics": {
                    "block_recall": 1.0,
                    "allow_recall": 1.0,
                    "category_exact_match": 1.0,
                },
            }
        ),
    )


def test_collect_portfolio_readiness_accepts_required_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {"offline_rag": {"ok": True}}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["portfolio_readiness_check"] is True
    assert report["failed"] == []
    assert "cloud_deployment" in report["deferred"]


def test_collect_portfolio_readiness_reports_missing_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)
    (tmp_path / "Dockerfile").unlink()

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": False, "lanes": {}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["portfolio_readiness_check"] is False
    failed = {item["id"] for item in report["failed"]}
    assert {"gate_status", "dockerfile"}.issubset(failed)


def test_portfolio_check_cli_writes_report(tmp_path: Path, monkeypatch) -> None:
    _minimal_ready_root(tmp_path)
    out = tmp_path / "portfolio_readiness.json"

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {}},
    )

    rc = main(["--root", str(tmp_path), "--out", str(out)])

    assert rc == 0
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["portfolio_readiness_check"] is True
