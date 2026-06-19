from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.security_reliability import evaluate_security_reliability, main


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_reliability_inputs(root: Path) -> None:
    _write(
        root / "artifacts/eval_agent_stress/replay.jsonl",
        '{"id": "abstain", "ok": true}\n{"id": "direct_rag", "ok": true}\n',
    )
    _write(
        root / "artifacts/service_ops/summary.json",
        json.dumps({"service_ops_complete": True}, ensure_ascii=False),
    )


def test_evaluate_security_reliability_writes_deepening_artifacts(
    tmp_path: Path,
) -> None:
    _write_reliability_inputs(tmp_path)

    summary = evaluate_security_reliability(root=tmp_path)

    assert summary["security_reliability_complete"] is True
    assert summary["metrics"]["redteam_case_count"] == 20
    assert summary["metrics"]["prompt_injection_block_recall"] == 1.0
    assert summary["metrics"]["secrets_pii_leak_count"] == 0
    assert summary["metrics"]["fallback_recovery_pass"] == 1.0
    assert summary["metrics"]["deterministic_replay_pass"] == 1.0
    redteam = (tmp_path / "artifacts/reliability_security/redteam.jsonl").read_text(
        encoding="utf-8"
    )
    assert "[REDACTED]" in redteam


def test_evaluate_security_reliability_fails_closed_without_replay(
    tmp_path: Path,
) -> None:
    summary = evaluate_security_reliability(root=tmp_path)

    assert summary["security_reliability_complete"] is False
    assert "fallback_recovery_pass" in summary["failed"]
    assert "deterministic_replay_pass" in summary["failed"]


def test_security_reliability_cli_returns_nonzero_on_failed_summary(
    tmp_path: Path,
) -> None:
    rc = main(["--root", str(tmp_path)])

    assert rc == 1
