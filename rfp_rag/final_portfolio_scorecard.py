from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_OUT = Path("artifacts/final_portfolio_scorecard/summary.json")

SCORE_THRESHOLD = 90

DIMENSION_WEIGHTS = {
    "business_problem_sharpness": 10,
    "source_first_rag_quality": 20,
    "agentic_engineering_depth": 20,
    "evaluation_rigor": 15,
    "production_operations": 15,
    "guardrails_security": 10,
    "hiring_presentation": 10,
}

CLAIM_BOUNDARY = "public_safe_hosted_reviewer_demo"

PUBLIC_DOCS = [
    "README.md",
    "docs/portfolio/senior-reviewer-pack.md",
    "docs/portfolio/company-fit-matrix.md",
    "docs/portfolio/korean-one-page-case-study.md",
    "docs/portfolio/demo-runbook.md",
    "docs/portfolio/resume-interview-bullets.md",
]

FORBIDDEN_CLAIM_PATTERNS = {
    "hosted_cloud_claim": re.compile(
        r"\b(hosted cloud production|hosted production service|cloud-deployed SaaS)\b",
        re.IGNORECASE,
    ),
    "live_traffic_slo_claim": re.compile(
        r"\b(live-traffic SLO|live traffic SLO|real user traffic)\b",
        re.IGNORECASE,
    ),
    "provider_billing_telemetry_claim": re.compile(
        r"\b(provider billing telemetry|live provider billing telemetry)\b",
        re.IGNORECASE,
    ),
    "reranker_quality_win_claim": re.compile(
        r"\b(reranker quality win|reranker win)\b",
        re.IGNORECASE,
    ),
}

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"OPENAI_API_KEY\s*="),
    re.compile(r"BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY"),
)

SAFE_NON_CLAIM_QUALIFIERS = (
    "not claim",
    "not claimed",
    "do not claim",
    "does not claim",
    "not hosted",
    "no hosted",
    "not yet proven",
    "without hosted production",
    "without approved",
    "requires separate",
    "requires hosted",
    "is implied without",
    "outside the current",
    "out of scope",
    "stay out of scope",
    "avoid until evidence exists",
    "non-claim",
    "별도 승인",
    "별도 승인/증거",
    "승인 후",
    "별도 phase",
    "아직",
    "claim이 아닙니다",
    "주장이 아닙니다",
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _complete(summary: dict[str, Any], field: str) -> bool:
    return summary.get(field) is True and not summary.get("failed")


def _metric(summary: dict[str, Any], field: str, default: float = 0.0) -> float:
    value = (summary.get("metrics") or {}).get(field)
    return float(value) if isinstance(value, int | float | bool) else default


def _all_paths_exist(root: Path, paths: list[str]) -> bool:
    return all((root / path).is_file() for path in paths)


def _doc_bundle_text(root: Path, docs: list[str]) -> str:
    return "\n\n".join(_read_text(root / rel) for rel in docs)


def _unqualified_production_grade_count(text: str) -> int:
    safe_qualifiers = (
        "rather than production-grade",
        "why not claim production-grade",
        "production-grade requires",
        *SAFE_NON_CLAIM_QUALIFIERS,
    )
    count = 0
    for line in text.splitlines():
        lower = line.lower()
        if "production-grade" in lower and not any(
            qualifier in lower for qualifier in safe_qualifiers
        ):
            count += 1
    return count


def _claim_counts(text: str) -> dict[str, float]:
    counts: dict[str, float] = {key: 0.0 for key in FORBIDDEN_CLAIM_PATTERNS}
    paragraphs = re.split(r"\n\s*\n", text)
    for paragraph in paragraphs:
        lower = " ".join(paragraph.lower().split())
        if any(qualifier in lower for qualifier in SAFE_NON_CLAIM_QUALIFIERS):
            continue
        for key, pattern in FORBIDDEN_CLAIM_PATTERNS.items():
            if pattern.search(paragraph):
                counts[key] += 1.0
    counts["unqualified_production_grade_claim"] = float(
        _unqualified_production_grade_count(text)
    )
    return counts


def _claim_boundary_pass(claim_manifest: dict[str, Any], text: str) -> bool:
    if claim_manifest.get("claim_level") != CLAIM_BOUNDARY:
        return False
    non_claims = claim_manifest.get("non_claims")
    required_false = (
        "hosted_cloud_production",
        "live_traffic_slo",
        "provider_billing_telemetry",
        "reranker_quality_win",
        "full_auth_rate_limit_session_operations",
    )
    if not isinstance(non_claims, dict) or any(
        non_claims.get(key) is not False for key in required_false
    ):
        return False
    return all(value == 0.0 for value in _claim_counts(text).values())


def _docs_claim_consistency_pass(
    root: Path, claim_manifest: dict[str, Any]
) -> tuple[bool, list[str]]:
    required_docs = claim_manifest.get("required_public_docs")
    if not isinstance(required_docs, list) or not required_docs:
        required_docs = PUBLIC_DOCS
    missing_or_drifted: list[str] = []
    for rel in [str(path) for path in required_docs]:
        text = _read_text(root / rel).lower()
        if not text:
            missing_or_drifted.append(rel)
            continue
        if "production-adjacent" not in text:
            missing_or_drifted.append(rel)
        if "hosted" not in text and "live-traffic" not in text:
            missing_or_drifted.append(rel)
    return (not missing_or_drifted, sorted(set(missing_or_drifted)))


def _public_package_redaction_pass(
    root: Path, package_manifest: dict[str, Any]
) -> tuple[bool, list[str]]:
    if package_manifest.get("public_safe") is not True:
        return False, ["public_safe"]
    artifacts = package_manifest.get("publishable_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return False, ["publishable_artifacts"]
    issues: list[str] = []
    for rel in [str(path) for path in artifacts]:
        path = root / rel
        if not path.is_file():
            issues.append(f"missing:{rel}")
            continue
        text = _read_text(path)
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            issues.append(f"secret_pattern:{rel}")
    excluded = package_manifest.get("excluded_from_public_package")
    if not isinstance(excluded, list) or not {
        ".env",
        "data/files",
        "artifacts/parsed_docs",
    } <= {str(item) for item in excluded}:
        issues.append("excluded_from_public_package")
    return (not issues, sorted(set(issues)))


def _ci_docker_smoke_present(root: Path) -> bool:
    ci_text = _read_text(root / ".github/workflows/ci.yml")
    return "docker build" in ci_text and 'pytest -m "not real"' in ci_text


def _dimension(ok: bool, weight: int, evidence: list[str]) -> dict[str, Any]:
    return {
        "score": weight if ok else 0,
        "weight": weight,
        "ok": ok,
        "evidence": evidence,
    }


def build_final_portfolio_scorecard(*, root: Path = Path(".")) -> dict[str, Any]:
    root = root.resolve()
    paths = {
        "claim_manifest": root / "docs/portfolio/claim-manifest.json",
        "public_package_manifest": root / "docs/portfolio/public-package-manifest.json",
        "stage2_quality": root / "artifacts/stage2_quality_scorecard/summary.json",
        "stage3_agent": root / "artifacts/stage3_agent_scorecard/summary.json",
        "stage4_ops_risk": root / "artifacts/stage4_ops_risk_scorecard/summary.json",
        "production_readiness": root / "artifacts/production_readiness/summary.json",
        "hosted_demo_smoke": root / "artifacts/hosted_demo_smoke/summary.json",
        "fresh_clone_smoke": root / "artifacts/fresh_clone_smoke/summary.json",
    }
    docs = PUBLIC_DOCS
    evidence_paths = {
        **{key: str(path.relative_to(root)) for key, path in paths.items()},
        "public_docs": docs,
        "ci_workflow": ".github/workflows/ci.yml",
    }

    claim_manifest = _read_json(paths["claim_manifest"])
    public_package = _read_json(paths["public_package_manifest"])
    stage2 = _read_json(paths["stage2_quality"])
    stage3 = _read_json(paths["stage3_agent"])
    stage4 = _read_json(paths["stage4_ops_risk"])
    production = _read_json(paths["production_readiness"])
    hosted_smoke = _read_json(paths["hosted_demo_smoke"])
    fresh_clone = _read_json(paths["fresh_clone_smoke"])
    doc_text = _doc_bundle_text(root, docs)

    claim_counts = _claim_counts(doc_text)
    docs_consistent, docs_consistency_issues = _docs_claim_consistency_pass(
        root, claim_manifest
    )
    public_safe, public_package_issues = _public_package_redaction_pass(
        root, public_package
    )

    metrics = {
        **claim_counts,
        "claim_boundary_pass": (
            1.0 if _claim_boundary_pass(claim_manifest, doc_text) else 0.0
        ),
        "docs_claim_consistency_pass": 1.0 if docs_consistent else 0.0,
        "public_package_redaction_pass": 1.0 if public_safe else 0.0,
        "fresh_clone_offline_smoke_pass": (
            1.0
            if _complete(fresh_clone, "fresh_clone_offline_smoke_complete")
            and fresh_clone.get("offline_only") is True
            else 0.0
        ),
        "ci_docker_runtime_smoke_present": 1.0
        if _ci_docker_smoke_present(root)
        else 0.0,
        "stage2_quality_scorecard_pass": (
            1.0 if _complete(stage2, "stage2_quality_scorecard_complete") else 0.0
        ),
        "stage3_agent_scorecard_pass": (
            1.0 if _complete(stage3, "stage3_agent_scorecard_complete") else 0.0
        ),
        "stage4_ops_risk_scorecard_pass": (
            1.0 if _complete(stage4, "stage4_ops_risk_scorecard_complete") else 0.0
        ),
        "production_readiness_pass": (
            1.0
            if _complete(production, "production_facing_readiness_complete")
            else 0.0
        ),
        "hosted_demo_smoke_pass": (
            1.0
            if _complete(hosted_smoke, "hosted_demo_smoke_complete")
            and (hosted_smoke.get("metrics") or {}).get("reviewer_token_boundary_pass")
            == 1.0
            and (hosted_smoke.get("metrics") or {}).get("public_safe_sources_pass")
            == 1.0
            else 0.0
        ),
        "source_first_quality_floor": min(
            _metric(stage2, "parser_average_quality_score"),
            _metric(stage2, "context_precision_at5"),
            _metric(stage2, "context_recall_at5"),
            _metric(stage2, "citation_precision_proxy"),
        ),
        "agent_workflow_floor": min(
            _metric(stage3, "trajectory_pass_rate"),
            _metric(stage3, "required_replay_coverage"),
            _metric(stage3, "hitl_approval_convergence"),
        ),
        "guardrail_security_floor": min(
            1.0 if _metric(stage4, "secret_pii_leak_count") == 0 else 0.0,
            1.0 if _metric(stage4, "tool_policy_violation_count") == 0 else 0.0,
            1.0 if _metric(stage4, "unresolved_unaccepted_alert_count") == 0 else 0.0,
            _metric(stage4, "public_exposure_requires_approval"),
        ),
    }

    docs_present = _all_paths_exist(root, docs)
    dimensions = {
        "business_problem_sharpness": _dimension(
            docs_present
            and metrics["claim_boundary_pass"] == 1.0
            and "source-first" in doc_text.lower()
            and "korean public rfp" in doc_text.lower(),
            DIMENSION_WEIGHTS["business_problem_sharpness"],
            ["README.md", "docs/portfolio/claim-manifest.json"],
        ),
        "source_first_rag_quality": _dimension(
            metrics["stage2_quality_scorecard_pass"] == 1.0
            and metrics["source_first_quality_floor"] >= 0.90,
            DIMENSION_WEIGHTS["source_first_rag_quality"],
            ["artifacts/stage2_quality_scorecard/summary.json"],
        ),
        "agentic_engineering_depth": _dimension(
            metrics["stage3_agent_scorecard_pass"] == 1.0
            and metrics["agent_workflow_floor"] == 1.0,
            DIMENSION_WEIGHTS["agentic_engineering_depth"],
            ["artifacts/stage3_agent_scorecard/summary.json"],
        ),
        "evaluation_rigor": _dimension(
            metrics["stage2_quality_scorecard_pass"] == 1.0
            and metrics["stage3_agent_scorecard_pass"] == 1.0
            and metrics["fresh_clone_offline_smoke_pass"] == 1.0,
            DIMENSION_WEIGHTS["evaluation_rigor"],
            [
                "artifacts/stage2_quality_scorecard/summary.json",
                "artifacts/stage3_agent_scorecard/summary.json",
                "artifacts/fresh_clone_smoke/summary.json",
            ],
        ),
        "production_operations": _dimension(
            metrics["production_readiness_pass"] == 1.0
            and metrics["hosted_demo_smoke_pass"] == 1.0
            and metrics["stage4_ops_risk_scorecard_pass"] == 1.0
            and metrics["ci_docker_runtime_smoke_present"] == 1.0,
            DIMENSION_WEIGHTS["production_operations"],
            [
                "artifacts/production_readiness/summary.json",
                "artifacts/hosted_demo_smoke/summary.json",
                "artifacts/stage4_ops_risk_scorecard/summary.json",
                ".github/workflows/ci.yml",
            ],
        ),
        "guardrails_security": _dimension(
            metrics["stage4_ops_risk_scorecard_pass"] == 1.0
            and metrics["guardrail_security_floor"] == 1.0
            and metrics["public_package_redaction_pass"] == 1.0,
            DIMENSION_WEIGHTS["guardrails_security"],
            [
                "artifacts/stage4_ops_risk_scorecard/summary.json",
                "docs/portfolio/public-package-manifest.json",
            ],
        ),
        "hiring_presentation": _dimension(
            metrics["docs_claim_consistency_pass"] == 1.0
            and metrics["public_package_redaction_pass"] == 1.0
            and docs_present,
            DIMENSION_WEIGHTS["hiring_presentation"],
            PUBLIC_DOCS,
        ),
    }
    score_total = sum(int(item["score"]) for item in dimensions.values())
    metrics["score_total"] = float(score_total)
    for name, item in dimensions.items():
        metrics[f"dimension_{name}"] = float(item["score"])

    failed = [
        key for key, value in metrics.items() if key.endswith("_pass") and value != 1.0
    ]
    failed.extend(
        f"dimension:{name}" for name, item in dimensions.items() if not item["ok"]
    )
    if score_total < SCORE_THRESHOLD:
        failed.append("score_total")
    missing = [
        name
        for name, path in paths.items()
        if not path.exists() or (path.is_file() and path.stat().st_size == 0)
    ]
    failed.extend(f"missing:{name}" for name in missing)

    return {
        "final_portfolio_scorecard_complete": not failed,
        "stage5_schema_version": "senior-final-portfolio-scorecard-v1",
        "claim_boundary": claim_manifest.get("claim_level", ""),
        "score_total": score_total,
        "score_threshold": SCORE_THRESHOLD,
        "dimensions": dimensions,
        "metrics": metrics,
        "thresholds": {
            "score_total": SCORE_THRESHOLD,
            **{
                f"dimension_{name}": weight
                for name, weight in DIMENSION_WEIGHTS.items()
            },
            **{key: 0.0 for key in claim_counts},
            **{
                key: 1.0
                for key in metrics
                if key.endswith("_pass") or key in {"ci_docker_runtime_smoke_present"}
            },
        },
        "failed": sorted(set(failed)),
        "evidence_paths": evidence_paths,
        "docs_consistency_issues": docs_consistency_issues,
        "public_package_issues": public_package_issues,
        "non_claims": {
            "hosted_cloud_production": False,
            "live_traffic_slo": False,
            "provider_billing_telemetry": False,
            "reranker_quality_win": False,
            "full_auth_rate_limit_session_operations": False,
        },
        "notes": [
            "This scorecard is deterministic and credential-free.",
            "It intentionally scores production-adjacent local/container evidence, not hosted production.",
            "It avoids depending on portfolio_check output to prevent circular readiness claims.",
        ],
    }


def write_final_portfolio_scorecard(
    *, root: Path = Path("."), out: Path | None = None
) -> dict[str, Any]:
    root = root.resolve()
    summary = build_final_portfolio_scorecard(root=root)
    _write_json(out or root / DEFAULT_OUT, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate final senior portfolio evidence into a weighted scorecard."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    summary = write_final_portfolio_scorecard(root=args.root, out=args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["final_portfolio_scorecard_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
