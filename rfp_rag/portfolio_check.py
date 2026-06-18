from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rfp_rag.gate_status import collect_gate_status


DEFERRED_GAPS = [
    {
        "id": "cloud_deployment",
        "reason": "external cloud credentials/spend are intentionally out of scope until approved",
    },
    {
        "id": "public_dashboard",
        "reason": "broad UI/dashboard scope requires a separate product decision",
    },
]

SECOND_STAGE_GATES = [
    {
        "id": "eval_stage2_coverage",
        "path": "artifacts/eval_stage2/coverage.json",
        "complete_field": "eval_set_audit_complete",
        "required_fields": ("eval_set_hash", "metrics", "thresholds", "failed"),
    },
    {
        "id": "eval_stage2_real",
        "path": "artifacts/eval_stage2_real/metrics.json",
        "complete_field": "holdout_quality_complete",
        "required_fields": (
            "eval_set_hash",
            "thresholds_met",
            "per_slice_failed",
            "generation_model_id",
            "judge_model_id",
            "embedding_model_id",
            "prompt_template_hash",
            "metrics",
            "thresholds",
            "failed",
        ),
        "required_metric_fields": (
            "judge_coverage_faithfulness_min_by_answerable_slice",
            "judge_coverage_answer_relevancy_min_by_answerable_slice",
        ),
    },
    {
        "id": "agent_stress",
        "path": "artifacts/eval_agent_stress/metrics.json",
        "complete_field": "agent_stress_complete",
        "required_fields": ("metrics", "thresholds", "failed"),
    },
    {
        "id": "retrieval_bakeoff",
        "path": "artifacts/retrieval_bakeoff/summary.json",
        "complete_field": "retrieval_bakeoff_complete",
        "required_fields": ("decision", "metrics", "thresholds", "failed"),
    },
    {
        "id": "visual_quality",
        "path": "artifacts/visual_quality/summary.json",
        "complete_field": "visual_quality_complete",
        "required_fields": ("metrics", "thresholds", "failed"),
    },
    {
        "id": "service_ops",
        "path": "artifacts/service_ops/summary.json",
        "complete_field": "service_ops_complete",
        "required_fields": ("metrics", "thresholds", "failed"),
    },
    {
        "id": "security_redteam",
        "path": "artifacts/security_redteam/summary.json",
        "complete_field": "security_redteam_complete",
        "required_fields": ("metrics", "thresholds", "failed"),
    },
    {
        "id": "cost_budget",
        "path": "artifacts/cost_budget/summary.json",
        "complete_field": "cost_budget_complete",
        "required_fields": ("metrics", "thresholds", "failed"),
    },
]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _check_file(root: Path, rel: str) -> dict[str, Any]:
    path = root / rel
    check_id = (
        rel.replace("/", "_").replace(".", "_").replace("-", "_").strip("_").lower()
    )
    return {"id": check_id, "ok": path.is_file(), "path": rel}


def _check_text(root: Path, rel: str, needle: str, check_id: str) -> dict[str, Any]:
    path = root / rel
    ok = path.is_file() and needle in path.read_text(encoding="utf-8")
    return {"id": check_id, "ok": ok, "path": rel, "needle": needle}


def _second_stage_gate_issues(
    gate: dict[str, Any],
    summary: dict[str, Any],
    coverage_hash: str | None,
) -> list[str]:
    issues: list[str] = []
    complete_field = gate["complete_field"]
    if summary.get(complete_field) is not True:
        issues.append(complete_field)
    for field in gate.get("required_fields", ()):
        if field not in summary or summary.get(field) in (None, ""):
            issues.append(field)
    failed = summary.get("failed")
    if failed:
        issues.append("failed")
    if gate["id"] == "eval_stage2_real":
        if summary.get("thresholds_met") is not True:
            issues.append("thresholds_met")
        if summary.get("per_slice_failed") != []:
            issues.append("per_slice_failed")
        if coverage_hash and summary.get("eval_set_hash") != coverage_hash:
            issues.append("eval_set_hash_mismatch")
        metrics = summary.get("metrics")
        if not isinstance(metrics, dict):
            issues.append("metrics")
        else:
            for field in gate.get("required_metric_fields", ()):
                if metrics.get(field) is None:
                    issues.append(field)
        prompt_hash = summary.get("prompt_template_hash")
        if not isinstance(prompt_hash, str) or len(prompt_hash) != 64:
            issues.append("prompt_template_hash")
    return sorted(set(issues))


def _collect_second_stage_readiness(root: Path) -> dict[str, Any]:
    present: list[str] = []
    missing: list[str] = []
    failed: list[str] = []
    details: list[dict[str, Any]] = []
    coverage_summary = _read_json(root / "artifacts/eval_stage2/coverage.json")
    coverage_hash = coverage_summary.get("eval_set_hash")
    if not isinstance(coverage_hash, str) or not coverage_hash:
        coverage_hash = None
    for gate in SECOND_STAGE_GATES:
        path = root / gate["path"]
        if not path.exists():
            missing.append(gate["id"])
            details.append({**gate, "present": False, "ok": False})
            continue
        summary = _read_json(path)
        issues = _second_stage_gate_issues(gate, summary, coverage_hash)
        ok = not issues
        present.append(gate["id"])
        if not ok:
            failed.append(gate["id"])
        details.append(
            {
                **gate,
                "present": True,
                "ok": ok,
                "issues": issues,
                "failed": summary.get("failed") or [],
            }
        )
    return {
        "complete": not missing and not failed,
        "present": present,
        "missing": missing,
        "failed": failed,
        "details": details,
    }


def collect_portfolio_readiness(root: Path = Path(".")) -> dict[str, Any]:
    root = root.resolve()
    checks: list[dict[str, Any]] = []

    gate_status = collect_gate_status(root)
    checks.append(
        {
            "id": "gate_status",
            "ok": bool(gate_status.get("overall_ok")),
            "path": "python3 -m rfp_rag.gate_status",
        }
    )

    guardrail = _read_json(root / "artifacts/guardrails/summary.json")
    checks.append(
        {
            "id": "guardrail_regression",
            "ok": bool(guardrail.get("guardrail_regression_complete")),
            "path": "artifacts/guardrails/summary.json",
            "metrics": guardrail.get("metrics") or {},
        }
    )

    checks.extend(
        [
            _check_file(root, "Dockerfile"),
            _check_file(root, ".github/workflows/ci.yml"),
            _check_file(root, "docs/architecture/system-architecture.md"),
            _check_file(root, "docs/adr/0014-fastapi-service-surface.md"),
            _check_file(root, "docs/adr/0015-docker-ci-baseline.md"),
            _check_file(root, "docs/adr/0016-mcp-style-ops-tool-server.md"),
            _check_text(
                root,
                "README.md",
                "docs/architecture/system-architecture.md",
                "readme_architecture_link",
            ),
            _check_text(
                root,
                "REPORT.md",
                "Architecture evidence map",
                "report_architecture_section",
            ),
            _check_text(
                root,
                ".github/workflows/ci.yml",
                'pytest -m "not real"',
                "ci_no_real_tests",
            ),
            _check_text(
                root,
                ".github/workflows/ci.yml",
                "docker build",
                "ci_docker_build",
            ),
        ]
    )

    failed = [check for check in checks if not check["ok"]]
    second_stage = _collect_second_stage_readiness(root)
    return {
        "portfolio_readiness_check": not failed,
        "root": str(root),
        "checks": checks,
        "failed": failed,
        "second_stage_readiness": second_stage,
        "deferred": [gap["id"] for gap in DEFERRED_GAPS],
        "deferred_details": DEFERRED_GAPS,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check local senior-portfolio evidence bundle readiness."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--out", type=Path, default=Path("artifacts/portfolio_readiness.json")
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    report = collect_portfolio_readiness(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if report["portfolio_readiness_check"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
