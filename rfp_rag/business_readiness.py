from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_OUT = Path("artifacts/business_readiness/summary.json")

REQUIRED_DOCS = {
    "case_study": Path("docs/portfolio/case-study.md"),
    "company_fit_matrix": Path("docs/portfolio/company-fit-matrix.md"),
    "senior_reviewer_pack": Path("docs/portfolio/senior-reviewer-pack.md"),
    "freelance_offer_pack": Path("docs/portfolio/freelance-offer-pack.md"),
    "startup_validation_plan": Path("docs/portfolio/startup-validation-plan.md"),
}

REQUIRED_DOC_TERMS = {
    "case_study": ["agentic rag", "source-first"],
    "company_fit_matrix": ["senior ai agent engineer", "outcome lens"],
    "senior_reviewer_pack": ["reviewer", "evidence"],
    "freelance_offer_pack": [
        "document rag diagnostic",
        "internal rag mvp",
        "agentic workflow automation",
    ],
    "startup_validation_plan": [
        "pilot gate",
        "full saas readiness: not yet.",
    ],
}

REQUIRED_ARTIFACTS = {
    "final_portfolio_scorecard": Path(
        "artifacts/final_portfolio_scorecard/summary.json"
    ),
    "hosted_demo_smoke": Path("artifacts/hosted_demo_smoke/summary.json"),
    "fresh_clone_smoke": Path("artifacts/fresh_clone_smoke/summary.json"),
    "production_readiness": Path("artifacts/production_readiness/summary.json"),
    "stage4_ops_risk_scorecard": Path(
        "artifacts/stage4_ops_risk_scorecard/summary.json"
    ),
}

THRESHOLDS = {
    "employment": 90,
    "freelance": 80,
    "startup_discovery": 65,
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _complete(payload: dict[str, Any], key: str) -> bool:
    return (
        key in payload
        and payload.get(key) is True
        and "failed" in payload
        and payload.get("failed") == []
    )


def _has_markdown_headings(text: str, minimum: int = 2) -> bool:
    heading_count = sum(
        1 for line in text.splitlines() if line.lstrip().startswith("#")
    )
    return heading_count >= minimum


def _doc_present(root: Path, key: str) -> bool:
    path = root / REQUIRED_DOCS[key]
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8").strip()
    if len(text) < 120:
        return False
    if not _has_markdown_headings(text):
        return False
    lowered = text.lower()
    return all(term in lowered for term in REQUIRED_DOC_TERMS[key])


def _artifact_ready(
    payload: dict[str, Any], completion_key: str, *, require_metrics: bool = False
) -> bool:
    if not isinstance(payload, dict):
        return False
    if (
        completion_key not in payload
        or payload.get(completion_key) is not True
        or "failed" not in payload
        or payload.get("failed") != []
    ):
        return False
    if not require_metrics:
        return True
    metrics = payload.get("metrics")
    thresholds = payload.get("thresholds")
    return (
        isinstance(metrics, dict)
        and bool(metrics)
        and isinstance(thresholds, dict)
        and bool(thresholds)
    )


def _has_positive_metric(payload: dict[str, Any], metric: str) -> bool:
    metrics = payload.get("metrics")
    return isinstance(metrics, dict) and metrics.get(metric) == 1.0


def _hosted_demo_smoke_ready(payload: dict[str, Any]) -> bool:
    return (
        payload.get("hosted_demo_smoke_complete") is True
        and "failed" in payload
        and payload.get("failed") == []
        and isinstance(payload.get("observed_git_sha"), str)
        and payload.get("observed_git_sha").strip() != ""
        and _has_positive_metric(payload, "rate_limit_boundary_pass")
    )


def _fresh_clone_smoke_ready(payload: dict[str, Any]) -> bool:
    checks = payload.get("checks")
    return (
        payload.get("fresh_clone_offline_smoke_complete") is True
        and "failed" in payload
        and payload.get("failed") == []
        and payload.get("offline_only") is True
        and isinstance(payload.get("git_sha"), str)
        and payload.get("git_sha").strip() != ""
        and isinstance(checks, list)
        and bool(checks)
        and _has_positive_metric(payload, "pytest_not_real_pass")
    )


def _has_nontrivial_structure(value: Any) -> bool:
    if isinstance(value, dict) or isinstance(value, list) or isinstance(value, tuple):
        return bool(value)
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, bool):
        return value
    return False


def _component_has_evidence(component: dict[str, Any]) -> bool:
    return any(
        _has_nontrivial_structure(value)
        for key, value in component.items()
        if key
        in {
            "metrics",
            "evidence",
            "path",
            "open_alerts",
            "remediated_alerts",
            "dependency_alerts",
            "dependency_count",
            "open_critical_alerts",
            "scan_status",
        }
    )


def _production_readiness_ready(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False

    if (
        payload.get("production_facing_readiness_complete") is not True
        or "failed" not in payload
        or payload.get("failed") != []
    ):
        return False

    components = payload.get("components")
    if not isinstance(components, dict) or not components:
        return False

    component_keys = set(components)
    required_keys = {
        "deployment_readiness",
        "interview_demo_package",
        "dependency_security",
    }
    if not required_keys.issubset(component_keys):
        return False

    def component_ok(component: Any) -> bool:
        if not isinstance(component, dict):
            return False
        complete_flags = [
            value for key, value in component.items() if key.endswith("_complete")
        ]
        if not complete_flags:
            return False
        if not all(flag is True for flag in complete_flags):
            return False
        if "failed" in component and component.get("failed") != []:
            return False
        if "failed" not in component:
            return False
        if not _component_has_evidence(component):
            return False
        return True

    if not all(component_ok(components[key]) for key in required_keys):
        return False

    has_breadth = len(components) >= len(required_keys)
    has_non_empty_metrics = any(
        isinstance(component.get("metrics"), dict) and bool(component.get("metrics"))
        for component in components.values()
        if isinstance(component, dict)
    )

    return has_breadth and has_non_empty_metrics


def evaluate_business_readiness(root: Path = Path(".")) -> dict[str, Any]:
    root = root.resolve()
    artifacts = {
        key: _read_json(root / path) for key, path in REQUIRED_ARTIFACTS.items()
    }
    docs = {key: _doc_present(root, key) for key in REQUIRED_DOCS}

    final_score = artifacts["final_portfolio_scorecard"].get("score_total", 0)
    final_portfolio_scorecard_ok = (
        _artifact_ready(
            artifacts["final_portfolio_scorecard"],
            "final_portfolio_scorecard_complete",
        )
        and final_score >= 90
    )
    hosted_ok = _hosted_demo_smoke_ready(artifacts["hosted_demo_smoke"])
    fresh_clone_ok = _fresh_clone_smoke_ready(artifacts["fresh_clone_smoke"])
    production_ok = _production_readiness_ready(artifacts["production_readiness"])
    ops_risk_ok = _artifact_ready(
        artifacts["stage4_ops_risk_scorecard"],
        "stage4_ops_risk_scorecard_complete",
        require_metrics=True,
    )

    employment_score = 0
    employment_score += 30 if final_portfolio_scorecard_ok else 0
    employment_score += 20 if hosted_ok else 0
    employment_score += 15 if fresh_clone_ok else 0
    employment_score += 15 if production_ok else 0
    employment_score += 10 if docs["case_study"] else 0
    employment_score += 10 if docs["company_fit_matrix"] else 0

    freelance_score = 0
    freelance_score += 25 if hosted_ok else 0
    freelance_score += 20 if production_ok else 0
    freelance_score += 15 if ops_risk_ok else 0
    freelance_score += 25 if docs["freelance_offer_pack"] else 0
    freelance_score += 15 if docs["senior_reviewer_pack"] else 0

    startup_discovery_score = 0
    startup_discovery_score += 20 if docs["startup_validation_plan"] else 0
    startup_discovery_score += 15 if docs["case_study"] else 0
    startup_discovery_score += 15 if docs["freelance_offer_pack"] else 0
    startup_discovery_score += 15 if hosted_ok else 0
    startup_discovery_score += 10 if production_ok else 0
    startup_discovery_score += 10 if ops_risk_ok else 0
    startup_discovery_score += 15 if docs["company_fit_matrix"] else 0

    checks = {
        "case_study_present": docs["case_study"],
        "company_fit_matrix_present": docs["company_fit_matrix"],
        "senior_reviewer_pack_present": docs["senior_reviewer_pack"],
        "freelance_offer_pack_present": docs["freelance_offer_pack"],
        "startup_validation_plan_present": docs["startup_validation_plan"],
        "final_portfolio_scorecard_pass": final_portfolio_scorecard_ok,
        "final_portfolio_score_at_least_90": final_score >= 90,
        "hosted_demo_smoke_pass": hosted_ok,
        "fresh_clone_smoke_pass": fresh_clone_ok,
        "production_readiness_pass": production_ok,
        "ops_risk_scorecard_pass": ops_risk_ok,
    }
    scores = {
        "employment": employment_score,
        "freelance": freelance_score,
        "startup_discovery": startup_discovery_score,
    }
    failed = [key for key, value in checks.items() if not value]
    failed.extend(
        f"{key}_score_below_{threshold}"
        for key, threshold in THRESHOLDS.items()
        if scores[key] < threshold
    )
    failed = sorted(set(failed))

    return {
        "schema_version": "business-readiness-v1",
        "business_readiness_complete": not failed,
        "scores": scores,
        "thresholds": THRESHOLDS,
        "employment_ready": scores["employment"] >= THRESHOLDS["employment"],
        "freelance_ready": scores["freelance"] >= THRESHOLDS["freelance"],
        "startup_discovery_ready": scores["startup_discovery"]
        >= THRESHOLDS["startup_discovery"],
        "startup_saas_ready": False,
        "checks": checks,
        "evidence": {
            "employment": {
                "final_portfolio_scorecard_pass": final_portfolio_scorecard_ok,
                "hosted_demo_smoke": hosted_ok,
                "fresh_clone_smoke": fresh_clone_ok,
                "case_study": docs["case_study"],
                "company_fit_matrix": docs["company_fit_matrix"],
            },
            "freelance": {
                "hosted_demo_smoke": hosted_ok,
                "production_readiness": production_ok,
                "ops_risk_scorecard": ops_risk_ok,
                "offer_pack": docs["freelance_offer_pack"],
                "reviewer_pack": docs["senior_reviewer_pack"],
            },
            "startup": {
                "validation_plan": docs["startup_validation_plan"],
                "case_study": docs["case_study"],
                "offer_pack": docs["freelance_offer_pack"],
                "saas_production_evidence": False,
            },
        },
        "failed": failed,
        "non_claims": [
            "full_saas_production",
            "product_market_fit",
            "live_customer_revenue",
            "multi_tenant_security_review",
            "paid_cloud_slo",
        ],
    }


def write_business_readiness(
    root: Path = Path("."), out: Path = DEFAULT_OUT
) -> dict[str, Any]:
    summary = evaluate_business_readiness(root=root)
    target = root / out if not out.is_absolute() else out
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    summary = write_business_readiness(root=args.root, out=args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["business_readiness_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
