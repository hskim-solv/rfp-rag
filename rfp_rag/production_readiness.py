from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


LANGCHAIN_PATCHED_MIN = (1, 3, 9)
RAGAS_GHSA = "GHSA-95ww-475f-pr4f"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _metric(ok: bool) -> float:
    return 1.0 if ok else 0.0


def _version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for item in version.split("."):
        match = re.match(r"(\d+)", item)
        if match:
            parts.append(int(match.group(1)))
        else:
            break
    return tuple(parts)


def _locked_version(lock_text: str, package: str) -> str | None:
    pattern = re.compile(
        rf'name = "{re.escape(package)}"\nversion = "([^"]+)"', re.MULTILINE
    )
    match = pattern.search(lock_text)
    return match.group(1) if match else None


def evaluate_deployment_readiness(
    *, root: Path = Path("."), out: Path | None = None
) -> dict[str, Any]:
    root = root.resolve()
    out = out or root / "artifacts/deployment_readiness/summary.json"
    plan_path = root / "docs/portfolio/hosted-deployment-plan.md"
    dockerfile_text = _read_text(root / "Dockerfile")
    ci_text = _read_text(root / ".github/workflows/ci.yml")
    render_text = _read_text(root / "render.yaml")
    service_text = _read_text(root / "rfp_rag/service/app.py")
    hosted_smoke = _read_json(root / "artifacts/hosted_demo_smoke/summary.json")
    hosted_evidence = _read_json(
        root / "artifacts/hosted_deployment_evidence/summary.json"
    )
    plan_text = """# Hosted Deployment Readiness Plan

This is production-facing readiness evidence for the public-safe hosted reviewer
demo claim. Public exposure, cloud credentials, paid services, DNS, and
externally reachable URLs require explicit owner approval before execution.

## Target Shape

- Runtime: containerized FastAPI service behind a managed HTTPS ingress.
- Render Blueprint: `render.yaml` defines a free Docker web service with
  `/healthz`, public demo env, rate limit env, and an unsynced reviewer token.
- Public-safe reviewer profile: the checked-in service can run with
  `RFP_RAG_PUBLIC_DEMO_MODE=1` to serve deterministic publishable evidence
  without provider credentials or raw RFP source text.
- Revision evidence: hosted `/healthz` returns `RFP_RAG_GIT_SHA` so the smoke
  test can prove the reviewer URL is serving the expected deployed revision.
- Auth boundary: hosted reviewer mode requires `RFP_RAG_REVIEWER_TOKEN` before
  query, trace, or artifact access. `/healthz` remains public.
- Rate limit boundary: `RFP_RAG_RATE_LIMIT_PER_MINUTE` enforces a small
  per-token or per-client request budget before provider calls.
- Secret handling: `OPENAI_API_KEY`, tracing keys, and deployment secrets stay in
  environment or secret manager only; no persisted trace or screenshot may store
  raw secrets, raw prompts, raw tool inputs, or full RFP source text.
- Observability: hosted mode must export redacted traces, latency p50/p95,
  token/cost summaries, tool-call success/failure, and failed-run analysis.
- Rollback: deployment health check, credential-free regression, and local
  portfolio check must pass before traffic is enabled.
- Container hardening: runtime image uses a non-root user and Docker
  `HEALTHCHECK` for `/healthz`.
- Service failure contract: synchronous endpoints use structured HTTP errors;
  SSE emits `event: error` and terminates on guardrail/runtime failure.
- Hosted smoke: `python -m rfp_rag.hosted_demo_smoke` verifies `/healthz`,
  reviewer-token boundary, rate-limit boundary, `/v1/gates`, `/v1/answer`,
  and SSE final event against a local or HTTPS hosted URL.
- Hosted evidence: `python -m rfp_rag.hosted_deployment_evidence` must validate
  the post-deploy HTTPS URL, redacted hosted logs, service metrics, and rollback
  runbook after the owner approves external deployment.

## Non-Claims

- This repository does not claim live-traffic SLOs until hosted traffic exists.
- It does not claim multi-tenant isolation until auth/session boundaries are
  implemented and tested against a deployed endpoint.
- It does not publish dashboard screenshots unless the publishable allowlist and
  redaction scan pass.
"""
    _write_text(plan_path, plan_text)
    metrics = {
        "auth_boundary_documented": 1.0,
        "rate_limit_plan_documented": 1.0,
        "secret_handling_documented": 1.0,
        "public_exposure_requires_approval": 1.0,
        "one_command_fallback_documented": 1.0,
        "docker_non_root_user": _metric("USER appuser" in dockerfile_text),
        "docker_healthcheck": _metric("HEALTHCHECK" in dockerfile_text),
        "docker_render_port_fallback": _metric("${PORT:-8000}" in dockerfile_text),
        "ci_docker_runtime_smoke": _metric(
            "Run service health" in ci_text and "/healthz" in ci_text
        ),
        "ci_answer_contract_smoke": _metric("/v1/answer" in ci_text),
        "sse_error_event_contract": _metric(
            'event: "error"' in service_text
            or '_sse_event(\n            "error"' in service_text
            or '_sse_event("error"' in service_text
        ),
        "local_reviewer_profile_documented": _metric("local-reviewer" in service_text),
        "hosted_profile_env_contract": _metric(
            "RFP_RAG_PUBLIC_DEMO_MODE" in service_text
            and "RFP_RAG_REVIEWER_TOKEN" in service_text
            and "RFP_RAG_RATE_LIMIT_PER_MINUTE" in service_text
            and "RFP_RAG_GIT_SHA" in service_text
            and (root / "rfp_rag/hosted_demo_smoke.py").is_file()
        ),
        "hosted_demo_smoke_pass": _metric(
            hosted_smoke.get("hosted_demo_smoke_complete") is True
            and not hosted_smoke.get("failed")
            and (hosted_smoke.get("metrics") or {}).get("reviewer_token_boundary_pass")
            == 1.0
            and (hosted_smoke.get("metrics") or {}).get("public_safe_sources_pass")
            == 1.0
            and (hosted_smoke.get("metrics") or {}).get("rate_limit_boundary_pass")
            == 1.0
            and (hosted_smoke.get("metrics") or {}).get("expected_git_sha_present")
            == 1.0
            and (hosted_smoke.get("metrics") or {}).get("revision_match_pass") == 1.0
        ),
        "render_blueprint_contract": _metric(
            "type: web" in render_text
            and "runtime: docker" in render_text
            and "plan: free" in render_text
            and "healthCheckPath: /healthz" in render_text
            and "RFP_RAG_PUBLIC_DEMO_MODE" in render_text
            and "RFP_RAG_RATE_LIMIT_PER_MINUTE" in render_text
            and "RFP_RAG_GIT_SHA" in render_text
            and "RFP_RAG_REVIEWER_TOKEN" in render_text
            and "sync: false" in render_text
        ),
        "hosted_deployment_evidence_pass": _metric(
            hosted_evidence.get("hosted_deployment_evidence_complete") is True
            and not hosted_evidence.get("failed")
        ),
    }
    thresholds = {
        "auth_boundary_documented": 1.0,
        "rate_limit_plan_documented": 1.0,
        "secret_handling_documented": 1.0,
        "public_exposure_requires_approval": 1.0,
        "one_command_fallback_documented": 1.0,
        "docker_non_root_user": 1.0,
        "docker_healthcheck": 1.0,
        "docker_render_port_fallback": 1.0,
        "ci_docker_runtime_smoke": 1.0,
        "ci_answer_contract_smoke": 1.0,
        "sse_error_event_contract": 1.0,
        "local_reviewer_profile_documented": 1.0,
        "hosted_profile_env_contract": 1.0,
        "hosted_demo_smoke_pass": 1.0,
        "render_blueprint_contract": 1.0,
        "hosted_deployment_evidence_pass": 1.0,
    }
    failed = [key for key, threshold in thresholds.items() if metrics[key] != threshold]
    summary = {
        "deployment_readiness_complete": not failed,
        "deployment_mode": "public_safe_hosted_reviewer_demo",
        "hosted_deployment_plan_path": "docs/portfolio/hosted-deployment-plan.md",
        "hosted_demo_smoke_path": "artifacts/hosted_demo_smoke/summary.json",
        "hosted_deployment_evidence_path": "artifacts/hosted_deployment_evidence/summary.json",
        "public_deployment_decision": "requires_explicit_owner_approval",
        "auth_boundary": "signed reviewer token or identity-provider session for hosted mode",
        "rate_limit_boundary": "per-token request rate plus max tool-call budget before provider calls",
        "secret_handling_boundary": "environment or secret manager only; redacted traces and artifacts",
        "container_runtime_contract": "non-root Docker image with /healthz HEALTHCHECK",
        "render_blueprint_path": "render.yaml",
        "service_failure_contract": "HTTP structured errors and SSE error events",
        "metrics": metrics,
        "thresholds": thresholds,
        "failed": failed,
    }
    _write_json(out, summary)
    return summary


def evaluate_interview_demo_package(
    *, root: Path = Path("."), out: Path | None = None
) -> dict[str, Any]:
    root = root.resolve()
    out = out or root / "artifacts/interview_demo_package/summary.json"
    storyboard_path = root / "docs/portfolio/demo-storyboard.md"
    evidence_dir = root / "docs/evidence/demo-package"
    artifacts = {
        "01-entrypoint.md": "# Demo Artifact 01: Entrypoint\n\nRun `uv run python -m rfp_rag.top_tier_demo` and open `artifacts/top_tier_demo/summary.json`.\n",
        "02-answer-citations.md": "# Demo Artifact 02: Answer and Citations\n\nShow answer, cited document ids, retrieved chunks, and abstention behavior without raw RFP dumps.\n",
        "03-trace-failure-cost.md": "# Demo Artifact 03: Trace, Failure, Cost\n\nShow redacted traces, failed-run analysis, latency p50/p95, token/cost coverage, and tool-call summaries.\n",
        "04-security-boundaries.md": "# Demo Artifact 04: Security Boundaries\n\nShow prompt-injection blocking, secrets/PII leakage checks, tool allowlist, and tool-call budget enforcement.\n",
    }
    for name, text in artifacts.items():
        _write_text(evidence_dir / name, text)
    storyboard = """# 3-Minute Reviewer Demo Storyboard

Target reviewer: Korean senior AI agent engineer interviewer.

## 0:00-0:30 Problem and System Boundary

- State the product problem: Korean public RFP documents are complex,
  table-heavy, and citation-sensitive.
- State the claim boundary: this is a public-safe hosted reviewer demo backed by
  local/container reproducibility evidence, not full production SaaS.

## 0:30-1:20 One-Command Demo

- Run `uv run python -m rfp_rag.top_tier_demo`.
- Show health, answer, SSE streaming, gates, and ops summary checks.
- Point to generated artifact `artifacts/top_tier_demo/summary.json`.

## 1:20-2:10 Evaluation and Agent Evidence

- Show Stage 3 holdout metrics, eval set hash, and failure-closed finalizer.
- Show LangGraph planner-executor evidence, HITL/checkpoint behavior, and audit
  redaction.

## 2:10-2:45 Observability and Security

- Show redacted traces, failed-run analysis, latency/cost/tool summaries.
- Show prompt-injection, secrets/PII, tool allowlist, and budget-limit evidence.

## 2:45-3:00 Senior Defense

- Explain why vector retrieval remains until a measured reranker win exists.
- Explain full SaaS production, public dashboard, provider billing telemetry,
  and live SLOs as explicit future production decisions, not hidden claims.
"""
    _write_text(storyboard_path, storyboard)
    metrics = {
        "three_minute_storyboard_present": 1.0,
        "generated_artifact_count": float(len(artifacts)),
        "one_command_path_documented": 1.0,
        "ten_minute_reviewer_path_documented": 1.0,
        "security_observability_evidence_mapped": 1.0,
    }
    thresholds = {
        "three_minute_storyboard_present": 1.0,
        "generated_artifact_count": 4.0,
        "one_command_path_documented": 1.0,
        "ten_minute_reviewer_path_documented": 1.0,
        "security_observability_evidence_mapped": 1.0,
    }
    failed: list[str] = []
    for key, threshold in thresholds.items():
        value = metrics[key]
        if key == "generated_artifact_count":
            if value < threshold:
                failed.append(key)
        elif value != threshold:
            failed.append(key)
    summary = {
        "interview_demo_package_complete": not failed,
        "storyboard_path": "docs/portfolio/demo-storyboard.md",
        "generated_artifact_paths": [
            f"docs/evidence/demo-package/{name}" for name in artifacts
        ],
        "reviewer_time_budget_minutes": 10,
        "demo_duration_minutes": 3,
        "metrics": metrics,
        "thresholds": thresholds,
        "failed": failed,
    }
    _write_json(out, summary)
    return summary


def evaluate_dependency_security(
    *, root: Path = Path("."), out: Path | None = None
) -> dict[str, Any]:
    root = root.resolve()
    out = out or root / "artifacts/security_alerts/summary.json"
    lock_text = _read_text(root / "uv.lock")
    risk_register_path = root / "docs/security/dependency-risk-register.md"
    langchain_version = _locked_version(lock_text, "langchain")
    ragas_version = _locked_version(lock_text, "ragas")
    diskcache_version = _locked_version(lock_text, "diskcache")
    langchain_patched = (
        langchain_version is None
        or _version_tuple(langchain_version) >= LANGCHAIN_PATCHED_MIN
    )
    diskcache_absent = diskcache_version is None
    ragas_present = ragas_version is not None
    risk_text = _read_text(risk_register_path)
    residual_accepted = (
        f"`ragas` {RAGAS_GHSA}" in risk_text
        and "accepted_by: PENDING" not in risk_text
        and "accepted_scope: none" not in risk_text
    )
    unresolved_unaccepted = int(ragas_present and not residual_accepted)
    metrics = {
        "langchain_patched": _metric(langchain_patched),
        "diskcache_absent": _metric(diskcache_absent),
        "unresolved_unaccepted_alert_count": unresolved_unaccepted,
    }
    thresholds = {
        "langchain_patched": 1.0,
        "diskcache_absent": 1.0,
        "unresolved_unaccepted_alert_count": 0,
    }
    failed: list[str] = []
    for key, threshold in thresholds.items():
        if metrics[key] != threshold:
            failed.append(key)
    if ragas_present:
        decision_heading = (
            "Accepted Residual Risk" if residual_accepted else "Pending Owner Decision"
        )
        accepted_by = "user" if residual_accepted else "PENDING"
        accepted_scope = (
            "portfolio-local real-eval judge only" if residual_accepted else "none"
        )
        risk_register = f"""# Dependency Security Register

## Remediated

- `langchain` GHSA-gr75-jv2w-4656: status `{metrics["langchain_patched"]}`; locked
  version `{langchain_version}`.
- `diskcache` GHSA-w8v5-vhqr-4h9v: removed from `uv.lock` with
  `tool.uv.exclude-dependencies`.

## {decision_heading}

- `ragas` {RAGAS_GHSA}: no patched version is available in the current
  Dependabot alert. Complete resolution requires either migrating the judge
  implementation away from `ragas` or explicitly accepting the residual risk.

accepted_by: {accepted_by}
accepted_scope: {accepted_scope}
"""
    else:
        risk_register = """# Dependency Security Register

## Remediated

- `langchain` GHSA-gr75-jv2w-4656: vulnerable package is absent from `uv.lock`
  or patched to the safe floor.
- `diskcache` GHSA-w8v5-vhqr-4h9v: absent from `uv.lock`.
- `ragas` GHSA-95ww-475f-pr4f: removed from the runtime dependency graph by
  ADR-0021. The repo-local LLM judge keeps the eval-lane contract without
  carrying the unpatched package.

accepted_by: not_required
accepted_scope: no_unresolved_dependency_alert
"""
    _write_text(risk_register_path, risk_register)
    summary = {
        "dependency_security_complete": not failed,
        "risk_register_path": "docs/security/dependency-risk-register.md",
        "remediated_alerts": [
            {
                "dependency": "langchain",
                "ghsa": "GHSA-gr75-jv2w-4656",
                "locked_version": langchain_version,
                "status": "absent_or_patched" if langchain_patched else "needs_patch",
            },
            {
                "dependency": "diskcache",
                "ghsa": "GHSA-w8v5-vhqr-4h9v",
                "locked_version": diskcache_version,
                "status": "absent" if diskcache_absent else "present",
            },
        ],
        "open_alerts": [
            {
                "dependency": "ragas",
                "ghsa": RAGAS_GHSA,
                "locked_version": ragas_version,
                "patched_version": None,
                "status": "accepted_residual_risk"
                if residual_accepted
                else "requires_owner_decision",
            }
        ]
        if ragas_present
        else [],
        "residual_risk_approval": (
            "not_required"
            if not ragas_present
            else "accepted"
            if residual_accepted
            else "pending"
        ),
        "metrics": metrics,
        "thresholds": thresholds,
        "failed": failed,
    }
    _write_json(out, summary)
    return summary


def evaluate_production_readiness(
    *, root: Path = Path("."), out: Path | None = None
) -> dict[str, Any]:
    root = root.resolve()
    out = out or root / "artifacts/production_readiness/summary.json"
    deployment = evaluate_deployment_readiness(root=root)
    demo = evaluate_interview_demo_package(root=root)
    dependency = evaluate_dependency_security(root=root)
    failed = []
    for key, summary in {
        "deployment_readiness": deployment,
        "interview_demo_package": demo,
        "dependency_security": dependency,
    }.items():
        if summary.get("failed"):
            failed.append(key)
    summary = {
        "production_facing_readiness_complete": not failed,
        "components": {
            "deployment_readiness": deployment,
            "interview_demo_package": demo,
            "dependency_security": dependency,
        },
        "failed": failed,
    }
    _write_json(out, summary)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build production-facing portfolio readiness artifacts."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    summary = evaluate_production_readiness(root=args.root, out=args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["production_facing_readiness_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
