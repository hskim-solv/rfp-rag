from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from .contracts import REAL_CONTRACT_VERSION, offline_contract


def check_report(eval_dir: Path | str, readme: Path | str) -> dict[str, Any]:
    """Validate offline-contract (rfp-rag-offline-v1) evidence only.

    Real-lane (rfp-rag-real-v1) eval dirs are out of scope and are flagged as
    real_lane_eval_dir_not_supported rather than as contract tampering.
    """
    eval_dir = Path(eval_dir)
    readme = Path(readme)
    canonical_contract = offline_contract()
    contract_path = eval_dir / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8")) if contract_path.exists() else {}
    required_files = list(canonical_contract.get("required_eval_files", []))
    missing_files = [name for name in required_files if not (eval_dir / name).exists()]
    readme_text = readme.read_text(encoding="utf-8") if readme.exists() else ""
    # README must also document the real provider quality lane section (rfp-rag-real-v1).
    required_readme = (
        list(canonical_contract.get("required_commands", []))
        + list(canonical_contract.get("readme_markers", []))
        + [REAL_CONTRACT_VERSION]
    )
    missing_readme_snippets = [snippet for snippet in required_readme if snippet not in readme_text]
    metrics: dict[str, Any] = {}
    metrics_path = eval_dir / "metrics.json"
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metric_warnings: list[str] = []
    if contract.get("contract_version") != canonical_contract.get("contract_version"):
        if contract.get("contract_version") == REAL_CONTRACT_VERSION:
            # Not tampering: this checker validates offline evidence only.
            metric_warnings.append("real_lane_eval_dir_not_supported")
        else:
            metric_warnings.append("contract_version_mismatch")
    # evaluate.py writes the normalized lane ("offline"); accept the legacy
    # "fake_offline" alias too so old artifacts still trip the drift guards.
    offline_lane = metrics.get("provider_lane") in ("offline", "fake_offline")
    if offline_lane and metrics.get("rag_quality_complete") is True:
        metric_warnings.append("offline_must_not_claim_rag_quality_complete")
    if offline_lane and metrics.get("thresholds_applied") is True:
        metric_warnings.append("offline_must_not_apply_real_quality_thresholds")
    ok = not missing_files and not missing_readme_snippets and not metric_warnings
    return {
        "ok": ok,
        "missing_files": missing_files,
        "contract_version": contract.get("contract_version"),
        "expected_contract_version": canonical_contract.get("contract_version"),
        "missing_readme_snippets": missing_readme_snippets,
        "metric_warnings": metric_warnings,
        "offline_scaffold_complete": metrics.get("offline_scaffold_complete"),
        "rag_quality_complete": metrics.get("rag_quality_complete"),
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check RFP RAG report artifacts and README command evidence.")
    parser.add_argument("--eval", required=True, dest="eval_dir", type=Path)
    parser.add_argument("--readme", required=True, type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = check_report(args.eval_dir, args.readme)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
