from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.security_redteam import evaluate_security_redteam, main


def test_evaluate_security_redteam_writes_stage2_contract_artifact(
    tmp_path: Path,
) -> None:
    summary = evaluate_security_redteam(root=tmp_path)

    assert summary["security_redteam_complete"] is True
    assert summary["metrics"] == {
        "artifact_redaction_scan_pass": 1.0,
        "block_recall": 1.0,
        "malicious_document_pass": 1.0,
        "malicious_retrieved_evidence_pass": 1.0,
        "malicious_tool_output_pass": 1.0,
        "publishable_allowlist_pass": 1.0,
        "raw_persistence_count": 0,
        "retention_scope_pass": 1.0,
        "secret_pii_leak_count": 0,
        "tool_policy_violation_count": 0,
    }
    assert summary["failed"] == []
    assert (tmp_path / "artifacts/security_redteam/summary.json").is_file()
    assert (tmp_path / "artifacts/security_redteam/publishable_allowlist.md").is_file()
    assert (tmp_path / "artifacts/security_redteam/retention_scope.md").is_file()
    serialized = json.dumps(summary, ensure_ascii=False)
    assert "Ignore previous instructions" not in serialized
    assert "이전 지시를 무시" not in serialized
    previews = [case["question_preview"] for case in summary["guardrail_cases"]]
    assert set(previews) == {"[REDACTED]"}


def test_evaluate_security_redteam_fails_raw_persistent_secret_scan(
    tmp_path: Path,
) -> None:
    leaked = tmp_path / "artifacts/security_redteam/leaky_artifact.json"
    leaked.parent.mkdir(parents=True)
    leaked.write_text(
        '{"query":"OPENAI_API_KEY=sk-real-looking-secret"}', encoding="utf-8"
    )

    summary = evaluate_security_redteam(root=tmp_path, scan_paths=[leaked])

    assert summary["security_redteam_complete"] is False
    assert summary["metrics"]["secret_pii_leak_count"] == 1
    assert summary["metrics"]["raw_persistence_count"] == 1
    assert "artifact_redaction_scan_pass" in summary["failed"]


def test_security_redteam_cli_writes_summary(tmp_path: Path) -> None:
    rc = main(["--root", str(tmp_path)])

    assert rc == 0
    saved = json.loads(
        (tmp_path / "artifacts/security_redteam/summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved["security_redteam_complete"] is True
