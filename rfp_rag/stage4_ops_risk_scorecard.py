from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_OUT = Path("artifacts/stage4_ops_risk_scorecard/summary.json")

THRESHOLDS = {
    "observability_complete": 1.0,
    "trace_export_present": 1.0,
    "latency_p50_ms_recorded": 1.0,
    "latency_p95_ms_recorded": 1.0,
    "token_cost_recorded": 1.0,
    "tool_success_rate_recorded": 1.0,
    "failed_run_analysis_count": 5,
    "service_ops_complete": 1.0,
    "healthz_pass": 1.0,
    "answer_pass": 1.0,
    "stream_pass": 1.0,
    "gates_pass": 1.0,
    "ops_summary_pass": 1.0,
    "path_safety_pass": 1.0,
    "token_cost_distribution_recorded": 1.0,
    "security_redteam_complete": 1.0,
    "block_recall": 1.0,
    "malicious_document_pass": 1.0,
    "malicious_retrieved_evidence_pass": 1.0,
    "malicious_tool_output_pass": 1.0,
    "artifact_redaction_scan_pass": 1.0,
    "publishable_allowlist_pass": 1.0,
    "retention_scope_pass": 1.0,
    "secret_pii_leak_count": 0,
    "raw_persistence_count": 0,
    "tool_policy_violation_count": 0,
    "security_reliability_complete": 1.0,
    "redteam_case_count": 20,
    "prompt_injection_block_recall": 1.0,
    "secrets_pii_leak_count": 0,
    "fallback_recovery_pass": 1.0,
    "deterministic_replay_pass": 1.0,
    "cost_budget_complete": 1.0,
    "token_record_coverage": 1.0,
    "cost_record_coverage": 1.0,
    "budget_violation_count": 0,
    "dependency_security_complete": 1.0,
    "langchain_patched": 1.0,
    "diskcache_absent": 1.0,
    "unresolved_unaccepted_alert_count": 0,
    "deployment_readiness_complete": 1.0,
    "public_exposure_requires_approval": 1.0,
    "rate_limit_plan_documented": 1.0,
    "secret_handling_documented": 1.0,
    "sse_error_event_contract": 1.0,
}

CEILING_METRICS = {
    "secret_pii_leak_count",
    "raw_persistence_count",
    "tool_policy_violation_count",
    "secrets_pii_leak_count",
    "budget_violation_count",
    "unresolved_unaccepted_alert_count",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _float(value: Any, default: float = 0.0) -> float:
    return float(value) if isinstance(value, int | float | bool) else default


def _component_complete(summary: dict[str, Any], field: str) -> float:
    return 1.0 if summary.get(field) is True else 0.0


def _metric(summary: dict[str, Any], name: str) -> float:
    return _float((summary.get("metrics") or {}).get(name))


def _failed_component(summary: dict[str, Any]) -> bool:
    failed = summary.get("failed")
    return bool(failed)


def _evaluate_thresholds(metrics: dict[str, float]) -> list[str]:
    failed: list[str] = []
    for key, threshold in THRESHOLDS.items():
        value = metrics.get(key)
        if value is None:
            failed.append(key)
        elif key in CEILING_METRICS:
            if value > threshold:
                failed.append(key)
        elif value < threshold:
            failed.append(key)
    return failed


def build_stage4_ops_risk_scorecard(*, root: Path = Path(".")) -> dict[str, Any]:
    root = root.resolve()
    paths = {
        "observability": root / "artifacts/observability/summary.json",
        "service_ops": root / "artifacts/service_ops/summary.json",
        "security_redteam": root / "artifacts/security_redteam/summary.json",
        "reliability_security": root / "artifacts/reliability_security/summary.json",
        "cost_budget": root / "artifacts/cost_budget/summary.json",
        "dependency_security": root / "artifacts/security_alerts/summary.json",
        "deployment_readiness": root / "artifacts/deployment_readiness/summary.json",
    }
    missing = [
        name
        for name, path in paths.items()
        if not path.exists() or (path.is_file() and path.stat().st_size == 0)
    ]

    observability = _read_json(paths["observability"])
    service_ops = _read_json(paths["service_ops"])
    security_redteam = _read_json(paths["security_redteam"])
    reliability_security = _read_json(paths["reliability_security"])
    cost_budget = _read_json(paths["cost_budget"])
    dependency_security = _read_json(paths["dependency_security"])
    deployment_readiness = _read_json(paths["deployment_readiness"])

    metrics = {
        "observability_complete": _component_complete(
            observability, "observability_complete"
        ),
        "trace_export_present": _metric(observability, "trace_export_present"),
        "latency_p50_ms_recorded": _metric(observability, "latency_p50_ms_recorded"),
        "latency_p95_ms_recorded": _metric(observability, "latency_p95_ms_recorded"),
        "token_cost_recorded": _metric(observability, "token_cost_recorded"),
        "tool_success_rate_recorded": _metric(
            observability, "tool_success_rate_recorded"
        ),
        "failed_run_analysis_count": _metric(
            observability, "failed_run_analysis_count"
        ),
        "service_ops_complete": _component_complete(
            service_ops, "service_ops_complete"
        ),
        "healthz_pass": _metric(service_ops, "healthz_pass"),
        "answer_pass": _metric(service_ops, "answer_pass"),
        "stream_pass": _metric(service_ops, "stream_pass"),
        "gates_pass": _metric(service_ops, "gates_pass"),
        "ops_summary_pass": _metric(service_ops, "ops_summary_pass"),
        "path_safety_pass": _metric(service_ops, "path_safety_pass"),
        "token_cost_distribution_recorded": _metric(
            service_ops, "token_cost_distribution_recorded"
        ),
        "latency_p50_ms": _metric(service_ops, "latency_p50_ms"),
        "latency_p95_ms": _metric(service_ops, "latency_p95_ms"),
        "security_redteam_complete": _component_complete(
            security_redteam, "security_redteam_complete"
        ),
        "block_recall": _metric(security_redteam, "block_recall"),
        "malicious_document_pass": _metric(security_redteam, "malicious_document_pass"),
        "malicious_retrieved_evidence_pass": _metric(
            security_redteam, "malicious_retrieved_evidence_pass"
        ),
        "malicious_tool_output_pass": _metric(
            security_redteam, "malicious_tool_output_pass"
        ),
        "artifact_redaction_scan_pass": _metric(
            security_redteam, "artifact_redaction_scan_pass"
        ),
        "publishable_allowlist_pass": _metric(
            security_redteam, "publishable_allowlist_pass"
        ),
        "retention_scope_pass": _metric(security_redteam, "retention_scope_pass"),
        "secret_pii_leak_count": _metric(security_redteam, "secret_pii_leak_count"),
        "raw_persistence_count": _metric(security_redteam, "raw_persistence_count"),
        "tool_policy_violation_count": _metric(
            security_redteam, "tool_policy_violation_count"
        ),
        "security_reliability_complete": _component_complete(
            reliability_security, "security_reliability_complete"
        ),
        "redteam_case_count": _metric(reliability_security, "redteam_case_count"),
        "prompt_injection_block_recall": _metric(
            reliability_security, "prompt_injection_block_recall"
        ),
        "secrets_pii_leak_count": _metric(
            reliability_security, "secrets_pii_leak_count"
        ),
        "fallback_recovery_pass": _metric(
            reliability_security, "fallback_recovery_pass"
        ),
        "deterministic_replay_pass": _metric(
            reliability_security, "deterministic_replay_pass"
        ),
        "cost_budget_complete": _component_complete(
            cost_budget, "cost_budget_complete"
        ),
        "token_record_coverage": _metric(cost_budget, "token_record_coverage"),
        "cost_record_coverage": _metric(cost_budget, "cost_record_coverage"),
        "budget_violation_count": _metric(cost_budget, "budget_violation_count"),
        "dependency_security_complete": _component_complete(
            dependency_security, "dependency_security_complete"
        ),
        "langchain_patched": _metric(dependency_security, "langchain_patched"),
        "diskcache_absent": _metric(dependency_security, "diskcache_absent"),
        "unresolved_unaccepted_alert_count": _metric(
            dependency_security, "unresolved_unaccepted_alert_count"
        ),
        "deployment_readiness_complete": _component_complete(
            deployment_readiness, "deployment_readiness_complete"
        ),
        "public_exposure_requires_approval": _metric(
            deployment_readiness, "public_exposure_requires_approval"
        ),
        "rate_limit_plan_documented": _metric(
            deployment_readiness, "rate_limit_plan_documented"
        ),
        "secret_handling_documented": _metric(
            deployment_readiness, "secret_handling_documented"
        ),
        "sse_error_event_contract": _metric(
            deployment_readiness, "sse_error_event_contract"
        ),
    }

    failed = [f"missing:{name}" for name in missing]
    failed.extend(_evaluate_thresholds(metrics))
    for name, summary in (
        ("observability", observability),
        ("service_ops", service_ops),
        ("security_redteam", security_redteam),
        ("reliability_security", reliability_security),
        ("cost_budget", cost_budget),
        ("dependency_security", dependency_security),
        ("deployment_readiness", deployment_readiness),
    ):
        if _failed_component(summary):
            failed.append(f"{name}:failed")

    return {
        "stage4_ops_risk_scorecard_complete": not failed,
        "metrics": metrics,
        "thresholds": THRESHOLDS,
        "failed": sorted(set(failed)),
        "evidence_paths": {
            key: str(path.relative_to(root)) for key, path in paths.items()
        },
        "method": {
            "operations": (
                "requires redacted traces, latency p50/p95 coverage, token/cost "
                "coverage, tool success reporting, local service smoke, and failed-run analysis"
            ),
            "risk": (
                "requires prompt-injection blocking, malicious evidence/tool checks, "
                "secrets/PII leak checks, publishability/retention checks, dependency "
                "security, and explicit public-exposure approval boundary"
            ),
        },
        "notes": [
            "This scorecard is deterministic and credential-free.",
            "It does not claim public hosted operation or live-traffic SLOs.",
            "Latency values are reported as local measured evidence, not production SLO thresholds.",
        ],
    }


def write_stage4_ops_risk_scorecard(
    *, root: Path = Path("."), out: Path | None = None
) -> dict[str, Any]:
    root = root.resolve()
    summary = build_stage4_ops_risk_scorecard(root=root)
    out = out or root / DEFAULT_OUT
    _write_json(out, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate Stage 4 operations and risk evidence into a senior portfolio scorecard."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    summary = write_stage4_ops_risk_scorecard(root=args.root, out=args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["stage4_ops_risk_scorecard_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
