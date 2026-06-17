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
    return {
        "portfolio_readiness_check": not failed,
        "root": str(root),
        "checks": checks,
        "failed": failed,
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
