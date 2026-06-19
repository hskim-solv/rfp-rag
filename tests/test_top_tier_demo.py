from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rfp_rag import top_tier_demo
from rfp_rag.top_tier_demo import main, run_top_tier_demo


def _service_summary(*, complete: bool = True) -> dict[str, Any]:
    return {
        "service_ops_complete": complete,
        "metrics": {
            "stream_pass": 1.0 if complete else 0.0,
            "gates_pass": 1.0 if complete else 0.0,
        },
        "failed": [] if complete else ["stream_pass"],
    }


def test_run_top_tier_demo_writes_one_command_artifact(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_service_ops(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["full_answer"] is False
        assert kwargs["full_gates"] is False
        return _service_summary()

    monkeypatch.setattr(top_tier_demo, "evaluate_service_ops", fake_service_ops)
    monkeypatch.setattr(
        top_tier_demo,
        "collect_portfolio_readiness",
        lambda root: {
            "portfolio_readiness_check": True,
            "top_tier_readiness": {"complete": False},
        },
    )

    summary = run_top_tier_demo(root=tmp_path)

    assert summary["top_tier_demo_complete"] is True
    assert summary["demo_mode"] == "one-command-local"
    assert (
        summary["public_exposure_decision"] == "local_one_command_until_cloud_approved"
    )
    assert summary["metrics"]["one_command_demo_pass"] == 1.0
    assert summary["metrics"]["streaming_demo_pass"] == 1.0
    assert summary["metrics"]["gate_summary_demo_pass"] == 1.0
    saved = json.loads(
        (tmp_path / "artifacts/top_tier_demo/summary.json").read_text(encoding="utf-8")
    )
    assert saved == summary


def test_run_top_tier_demo_fails_closed_when_portfolio_not_ready(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        top_tier_demo, "evaluate_service_ops", lambda **kwargs: _service_summary()
    )
    monkeypatch.setattr(
        top_tier_demo,
        "collect_portfolio_readiness",
        lambda root: {
            "portfolio_readiness_check": False,
            "top_tier_readiness": {"complete": False},
        },
    )

    summary = run_top_tier_demo(root=tmp_path)

    assert summary["top_tier_demo_complete"] is False
    assert "one_command_demo_pass" in summary["failed"]


def test_top_tier_demo_cli_returns_nonzero_on_failed_demo(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        top_tier_demo,
        "evaluate_service_ops",
        lambda **kwargs: _service_summary(complete=False),
    )
    monkeypatch.setattr(
        top_tier_demo,
        "collect_portfolio_readiness",
        lambda root: {
            "portfolio_readiness_check": True,
            "top_tier_readiness": {"complete": False},
        },
    )

    rc = main(["--root", str(tmp_path)])

    assert rc == 1
