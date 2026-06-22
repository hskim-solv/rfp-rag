from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_OUT = Path("artifacts/hosted_deployment_evidence/summary.json")


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


def _metric(ok: bool) -> float:
    return 1.0 if ok else 0.0


def _is_https_url(value: object) -> bool:
    return isinstance(value, str) and value.startswith("https://") and "." in value


def build_hosted_deployment_evidence(
    *, root: Path = Path("."), out: Path | None = None
) -> dict[str, Any]:
    root = root.resolve()
    out = out or root / DEFAULT_OUT
    hosted_smoke = _read_json(root / "artifacts/hosted_demo_smoke/summary.json")
    hosted_ops = _read_json(root / "artifacts/hosted_ops/summary.json")
    logs = hosted_ops.get("logs_evidence") or {}
    metrics_evidence = hosted_ops.get("metrics_evidence") or {}
    rollback = hosted_ops.get("rollback_evidence") or {}
    runbook_path = rollback.get("runbook_path")
    runbook_exists = isinstance(runbook_path, str) and (root / runbook_path).is_file()
    base_url = hosted_smoke.get("base_url")
    service_url = hosted_ops.get("service_url")

    metrics = {
        "https_url_present": _metric(
            _is_https_url(base_url) and base_url == service_url
        ),
        "hosted_smoke_pass": _metric(
            hosted_smoke.get("hosted_demo_smoke_complete") is True
            and not hosted_smoke.get("failed")
            and (hosted_smoke.get("metrics") or {}).get("reviewer_token_boundary_pass")
            == 1.0
            and (hosted_smoke.get("metrics") or {}).get("public_safe_sources_pass")
            == 1.0
        ),
        "deploy_smoke_success": _metric(
            hosted_ops.get("deploy_smoke_status") == "SUCCESS"
        ),
        "logs_redacted_pass": _metric(
            logs.get("redacted") is True
            and logs.get("healthz_2xx_seen") is True
            and logs.get("answer_2xx_seen") is True
            and logs.get("unauth_401_seen") is True
            and logs.get("secret_leak_count") == 0
            and logs.get("raw_rfp_text_seen") is False
        ),
        "metrics_visible_pass": _metric(
            metrics_evidence.get("redacted") is True
            and metrics_evidence.get("http_request_count_visible") is True
            and metrics_evidence.get("latency_visible") is True
            and metrics_evidence.get("error_count_visible") is True
        ),
        "rollback_runbook_pass": _metric(
            rollback.get("rollback_procedure_documented") is True
            and isinstance(rollback.get("last_known_good_git_sha"), str)
            and runbook_exists
        ),
        "secret_leak_count": float(logs.get("secret_leak_count") or 0),
        "raw_rfp_text_seen": 1.0 if logs.get("raw_rfp_text_seen") is True else 0.0,
    }
    thresholds = {
        "https_url_present": 1.0,
        "hosted_smoke_pass": 1.0,
        "deploy_smoke_success": 1.0,
        "logs_redacted_pass": 1.0,
        "metrics_visible_pass": 1.0,
        "rollback_runbook_pass": 1.0,
        "secret_leak_count": 0.0,
        "raw_rfp_text_seen": 0.0,
    }
    failed = [key for key, threshold in thresholds.items() if metrics[key] != threshold]
    summary = {
        "hosted_deployment_evidence_complete": not failed,
        "service_url": service_url or base_url,
        "hosted_demo_smoke_path": "artifacts/hosted_demo_smoke/summary.json",
        "hosted_ops_summary_path": "artifacts/hosted_ops/summary.json",
        "metrics": metrics,
        "thresholds": thresholds,
        "failed": failed,
    }
    _write_json(out, summary)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate hosted reviewer demo deployment evidence."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    summary = build_hosted_deployment_evidence(root=args.root, out=args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["hosted_deployment_evidence_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
