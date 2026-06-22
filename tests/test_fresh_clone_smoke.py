from __future__ import annotations

import csv
from pathlib import Path

from rfp_rag.fresh_clone_smoke import CommandResult, run_fresh_clone_smoke
from rfp_rag.synthetic_corpus import write_synthetic_corpus


def test_write_synthetic_corpus_creates_ci_parity_fixture(tmp_path: Path) -> None:
    summary = write_synthetic_corpus(root=tmp_path, doc_count=100)

    assert summary["synthetic_corpus_complete"] is True
    assert summary["doc_count"] == 100
    assert summary["hwp_count"] == 96
    assert summary["pdf_count"] == 4

    with (tmp_path / "data/data_list.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 100
    assert rows[0]["사업명"].startswith("한영대학교")
    assert (tmp_path / "data/files/ci_fixture_000.hwp").is_file()
    assert (tmp_path / "data/files/ci_fixture_099.pdf").is_file()


def test_run_fresh_clone_smoke_unsets_provider_env_and_records_checks(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    calls: list[dict] = []

    def runner(
        cmd: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: int,
    ) -> CommandResult:
        calls.append({"cmd": cmd, "cwd": cwd, "env": env, "timeout": timeout})
        if cmd == ["git", "rev-parse", "HEAD"]:
            return CommandResult(0, "abc123\n", "")
        return CommandResult(0, "ok\n", "")

    summary = run_fresh_clone_smoke(
        root=tmp_path,
        clone_dir=tmp_path / "clone",
        runner=runner,
        timeout=60,
    )

    assert summary["fresh_clone_offline_smoke_complete"] is True
    assert summary["failed"] == []
    assert summary["git_sha"] == "abc123"
    assert summary["metrics"]["no_credentials_required"] == 1.0
    assert summary["metrics"]["pytest_not_real_pass"] == 1.0
    assert summary["metrics"]["synthetic_corpus_pass"] == 1.0
    assert summary["provider_env_forbidden"] == [
        "LANGCHAIN_API_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "OPENAI_API_BASE",
        "OPENAI_API_KEY",
        "OPENAI_ORG",
        "OPENAI_ORGANIZATION",
    ]
    assert all("OPENAI_API_KEY" not in call["env"] for call in calls)


def test_run_fresh_clone_smoke_fails_closed_on_command_error(tmp_path: Path) -> None:
    def runner(
        cmd: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: int,
    ) -> CommandResult:
        if cmd == ["git", "rev-parse", "HEAD"]:
            return CommandResult(0, "abc123\n", "")
        if "pytest" in cmd:
            return CommandResult(1, "", "boom")
        return CommandResult(0, "ok\n", "")

    summary = run_fresh_clone_smoke(
        root=tmp_path,
        clone_dir=tmp_path / "clone",
        runner=runner,
        timeout=60,
    )

    assert summary["fresh_clone_offline_smoke_complete"] is False
    assert "pytest_not_real" in summary["failed"]
    assert summary["metrics"]["pytest_not_real_pass"] == 0.0
