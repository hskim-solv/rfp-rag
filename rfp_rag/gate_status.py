from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


GATE_SPECS = {
    "offline_rag": {
        "path": "artifacts/eval/metrics.json",
        "gate_key": "offline_scaffold_complete",
    },
    "real_rag": {
        "path": "artifacts/eval_real/metrics.json",
        "gate_key": "rag_quality_complete",
    },
    "agent_offline": {
        "path": "artifacts/eval_agent/metrics.json",
        "gate_key": "agent_lane_complete",
    },
    "visual_candidate": {
        "path": "artifacts/visual_tesseract_candidate_expanded_gate/summary.json",
        "gate_key": "ok",
    },
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _lane_status(root: Path, spec: dict[str, str]) -> dict[str, Any]:
    relative_path = spec["path"]
    gate_key = spec["gate_key"]
    path = root / relative_path
    base: dict[str, Any] = {
        "gate_key": gate_key,
        "path": relative_path,
        "present": path.exists(),
    }
    if not path.exists():
        return {**base, "ok": False, "value": None}
    try:
        payload = _read_json(path)
    except json.JSONDecodeError as exc:
        return {**base, "ok": False, "value": None, "error": str(exc)}

    value = payload.get(gate_key)
    status = {**base, "ok": value is True, "value": value}
    for optional_key in (
        "contract_version",
        "provider_lane",
        "decision",
        "thresholds_met",
        "evaluation_valid",
    ):
        if optional_key in payload:
            status[optional_key] = payload[optional_key]
    failed = payload.get("gate", {}).get("failed")
    if failed is not None:
        status["failed"] = failed
    return status


def collect_gate_status(root: Path | str = ".") -> dict[str, Any]:
    root_path = Path(root)
    lanes = {name: _lane_status(root_path, spec) for name, spec in GATE_SPECS.items()}
    return {
        "overall_ok": all(lane["ok"] for lane in lanes.values()),
        "root": str(root_path),
        "lanes": lanes,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Print read-only RFP RAG gate status as JSON."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    print(
        json.dumps(
            collect_gate_status(args.root),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
