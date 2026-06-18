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
    _write(
        root / ".github/workflows/ci.yml",
        'uv run pytest -m "not real"\ndocker build -t rfp-rag-service:ci .\n',
    )
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


def _write_complete_second_stage(root: Path) -> None:
    eval_set_hash = "stage2-eval-set-v1"
    complete_payloads = {
        "artifacts/eval_stage2/coverage.json": {
            "eval_set_audit_complete": True,
            "eval_set_hash": eval_set_hash,
            "metrics": {"query_count": 150},
            "thresholds": {"query_count": 150},
            "failed": [],
        },
        "artifacts/eval_stage2_real/metrics.json": {
            "holdout_quality_complete": True,
            "eval_set_hash": eval_set_hash,
            "thresholds_met": True,
            "per_slice_failed": [],
            "generation_model_id": "gpt-test",
            "judge_model_id": "judge-test",
            "embedding_model_id": "embed-test",
            "prompt_template_hash": "a" * 64,
            "metrics": {
                "judge_coverage_faithfulness_min_by_answerable_slice": 1.0,
                "judge_coverage_answer_relevancy_min_by_answerable_slice": 1.0,
            },
            "thresholds": {"recall@5": 0.95},
            "failed": [],
        },
        "artifacts/eval_agent_stress/metrics.json": {
            "agent_stress_complete": True,
            "metrics": {"pass_rate": 1.0},
            "thresholds": {"pass_rate": 1.0},
            "failed": [],
        },
        "artifacts/retrieval_bakeoff/summary.json": {
            "retrieval_bakeoff_complete": True,
            "decision": "keep_vector_until_reranker_wins",
            "metrics": {"winner_margin": 0.0},
            "thresholds": {"winner_margin": 0.0},
            "failed": [],
        },
        "artifacts/visual_quality/summary.json": {
            "visual_quality_complete": True,
            "metrics": {"visual_evidence_hit_rate": 1.0},
            "thresholds": {"visual_evidence_hit_rate": 0.9},
            "failed": [],
        },
        "artifacts/service_ops/summary.json": {
            "service_ops_complete": True,
            "metrics": {"healthz_pass": 1.0},
            "thresholds": {"healthz_pass": 1.0},
            "failed": [],
        },
        "artifacts/security_redteam/summary.json": {
            "security_redteam_complete": True,
            "metrics": {"block_recall": 1.0},
            "thresholds": {"block_recall": 1.0},
            "failed": [],
        },
        "artifacts/cost_budget/summary.json": {
            "cost_budget_complete": True,
            "metrics": {"cost_record_coverage": 1.0},
            "thresholds": {"cost_record_coverage": 1.0},
            "failed": [],
        },
    }
    for rel, payload in complete_payloads.items():
        _write(root / rel, json.dumps(payload))


def test_collect_portfolio_readiness_accepts_required_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {"offline_rag": {"ok": True}}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["local_evidence_bundle_check"] is True
    assert report["portfolio_readiness_check"] is False
    assert report["failed"] == []
    assert "cloud_deployment" in report["deferred"]
    assert report["second_stage_readiness"]["complete"] is False
    assert "security_redteam" in report["second_stage_readiness"]["missing"]


def test_collect_portfolio_readiness_requires_second_stage_for_top_level_ready(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)
    _write_complete_second_stage(tmp_path)

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {"offline_rag": {"ok": True}}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["local_evidence_bundle_check"] is True
    assert report["second_stage_readiness"]["complete"] is True
    assert report["portfolio_readiness_check"] is True


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
    assert report["local_evidence_bundle_check"] is False
    failed = {item["id"] for item in report["failed"]}
    assert {"gate_status", "dockerfile"}.issubset(failed)


def test_collect_portfolio_readiness_requires_docker_build_in_ci(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)
    _write(tmp_path / ".github/workflows/ci.yml", 'uv run pytest -m "not real"\n')

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["portfolio_readiness_check"] is False
    assert report["local_evidence_bundle_check"] is False
    failed = {item["id"] for item in report["failed"]}
    assert "ci_docker_build" in failed


def test_portfolio_check_cli_writes_report(tmp_path: Path, monkeypatch) -> None:
    _minimal_ready_root(tmp_path)
    _write_complete_second_stage(tmp_path)
    out = tmp_path / "portfolio_readiness.json"

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {}},
    )

    rc = main(["--root", str(tmp_path), "--out", str(out)])

    assert rc == 0
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["portfolio_readiness_check"] is True
    assert saved["local_evidence_bundle_check"] is True


def test_portfolio_check_reports_second_stage_separately(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)
    _write(
        tmp_path / "artifacts/security_redteam/summary.json",
        json.dumps(
            {
                "security_redteam_complete": False,
                "failed": ["secrets_block_recall"],
            }
        ),
    )

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["local_evidence_bundle_check"] is True
    assert report["portfolio_readiness_check"] is False
    assert report["second_stage_readiness"]["complete"] is False
    assert "security_redteam" in report["second_stage_readiness"]["present"]
    assert "security_redteam" in report["second_stage_readiness"]["failed"]


def test_second_stage_readiness_rejects_bool_only_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    _minimal_ready_root(tmp_path)
    stage2_flags = {
        "artifacts/eval_stage2/coverage.json": {"eval_set_audit_complete": True},
        "artifacts/eval_stage2_real/metrics.json": {"holdout_quality_complete": True},
        "artifacts/eval_agent_stress/metrics.json": {"agent_stress_complete": True},
        "artifacts/retrieval_bakeoff/summary.json": {
            "retrieval_bakeoff_complete": True
        },
        "artifacts/visual_quality/summary.json": {"visual_quality_complete": True},
        "artifacts/service_ops/summary.json": {"service_ops_complete": True},
        "artifacts/security_redteam/summary.json": {"security_redteam_complete": True},
        "artifacts/cost_budget/summary.json": {"cost_budget_complete": True},
    }
    for rel, payload in stage2_flags.items():
        _write(tmp_path / rel, json.dumps(payload))

    monkeypatch.setattr(
        "rfp_rag.portfolio_check.collect_gate_status",
        lambda root: {"overall_ok": True, "lanes": {}},
    )

    report = collect_portfolio_readiness(tmp_path)

    assert report["local_evidence_bundle_check"] is True
    assert report["portfolio_readiness_check"] is False
    assert report["second_stage_readiness"]["complete"] is False
    assert "eval_stage2_real" in report["second_stage_readiness"]["failed"]
    details = {item["id"]: item for item in report["second_stage_readiness"]["details"]}
    assert "eval_set_hash" in details["eval_stage2_real"]["issues"]
    assert "generation_model_id" in details["eval_stage2_real"]["issues"]
