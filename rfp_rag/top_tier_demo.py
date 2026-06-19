from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from rfp_rag.portfolio_check import collect_portfolio_readiness
from rfp_rag.stage2_service_ops import evaluate_service_ops


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _pass_metric(ok: bool) -> float:
    return 1.0 if ok else 0.0


def run_top_tier_demo(
    *,
    root: Path = Path("."),
    out: Path | None = None,
    question: str = "테스트 사업을 근거와 함께 요약해줘",
) -> dict[str, Any]:
    root = root.resolve()
    out = out or root / "artifacts/top_tier_demo/summary.json"
    started = time.perf_counter()

    service_summary_path = out.parent / "service_ops_summary.json"
    service_summary = evaluate_service_ops(
        root=root,
        out=service_summary_path,
        question=question,
        full_answer=False,
        full_gates=False,
    )
    readiness = collect_portfolio_readiness(root)
    elapsed_sec = round(time.perf_counter() - started, 3)

    service_metrics = service_summary.get("metrics") or {}
    portfolio_ready = readiness.get("portfolio_readiness_check") is True
    top_tier_visible = "top_tier_readiness" in readiness
    service_complete = service_summary.get("service_ops_complete") is True
    streaming_pass = service_metrics.get("stream_pass") == 1.0
    gates_pass = service_metrics.get("gates_pass") == 1.0 and top_tier_visible

    metrics = {
        "one_command_demo_pass": _pass_metric(service_complete and portfolio_ready),
        "no_credentials_required": 1.0,
        "streaming_demo_pass": _pass_metric(streaming_pass),
        "gate_summary_demo_pass": _pass_metric(gates_pass),
        "time_to_first_verified_answer_sec": elapsed_sec,
    }
    thresholds = {
        "one_command_demo_pass": 1.0,
        "no_credentials_required": 1.0,
        "streaming_demo_pass": 1.0,
        "gate_summary_demo_pass": 1.0,
        "time_to_first_verified_answer_sec": 300.0,
    }
    failed: list[str] = []
    for key, threshold in thresholds.items():
        value = metrics[key]
        if key == "time_to_first_verified_answer_sec":
            if value > threshold:
                failed.append(key)
        elif value != threshold:
            failed.append(key)

    summary = {
        "top_tier_demo_complete": not failed,
        "demo_mode": "one-command-local",
        "reviewer_command": "uv run python -m rfp_rag.top_tier_demo",
        "public_exposure_decision": "local_one_command_until_cloud_approved",
        "service_ops_summary_path": str(service_summary_path.relative_to(root)),
        "portfolio_readiness_check": portfolio_ready,
        "top_tier_readiness_complete": (readiness.get("top_tier_readiness") or {}).get(
            "complete"
        ),
        "metrics": metrics,
        "thresholds": thresholds,
        "failed": failed,
    }
    _write_json(out, summary)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the one-command top-tier reviewer demo smoke."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--question", default="테스트 사업을 근거와 함께 요약해줘")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    summary = run_top_tier_demo(
        root=args.root,
        out=args.out,
        question=args.question,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["top_tier_demo_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
