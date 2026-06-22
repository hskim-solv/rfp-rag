from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


DEFAULT_OUT = Path("artifacts/fresh_clone_smoke/summary.json")

FORBIDDEN_PROVIDER_ENV = [
    "LANGCHAIN_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "OPENAI_API_BASE",
    "OPENAI_API_KEY",
    "OPENAI_ORG",
    "OPENAI_ORGANIZATION",
]

THRESHOLDS = {
    "git_sha_recorded": 1.0,
    "git_clone_pass": 1.0,
    "checkout_head_pass": 1.0,
    "uv_sync_pass": 1.0,
    "synthetic_corpus_pass": 1.0,
    "ruff_format_pass": 1.0,
    "ruff_lint_pass": 1.0,
    "pytest_not_real_pass": 1.0,
    "no_credentials_required": 1.0,
}


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class Runner(Protocol):
    def __call__(
        self,
        cmd: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: int,
    ) -> CommandResult: ...


def _run_subprocess(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
) -> CommandResult:
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _offline_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in FORBIDDEN_PROVIDER_ENV:
        env.pop(key, None)
    env["RFP_RAG_OFFLINE_SMOKE"] = "1"
    return env


def _command_specs(clone_dir: Path) -> list[dict[str, Any]]:
    return [
        {
            "id": "git_clone",
            "cmd": ["git", "clone", "--local", "--no-hardlinks", ".", str(clone_dir)],
            "cwd": None,
        },
        {
            "id": "checkout_head",
            "cmd": ["git", "checkout", "--detach", "{git_sha}"],
            "cwd": clone_dir,
        },
        {
            "id": "uv_sync",
            "cmd": ["uv", "sync", "--frozen", "--group", "dev"],
            "cwd": clone_dir,
        },
        {
            "id": "synthetic_corpus",
            "cmd": ["uv", "run", "python", "-m", "rfp_rag.synthetic_corpus"],
            "cwd": clone_dir,
        },
        {
            "id": "ruff_format",
            "cmd": ["uv", "run", "ruff", "format", "--check", "rfp_rag", "tests"],
            "cwd": clone_dir,
        },
        {
            "id": "ruff_lint",
            "cmd": ["uv", "run", "ruff", "check", "rfp_rag", "tests"],
            "cwd": clone_dir,
        },
        {
            "id": "pytest_not_real",
            "cmd": ["uv", "run", "pytest", "-m", "not real", "-q"],
            "cwd": clone_dir,
        },
    ]


def _metric_name(command_id: str) -> str:
    return f"{command_id}_pass"


def _compact_output(text: str, *, limit: int = 1200) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[-limit:]


def _evaluate_thresholds(metrics: dict[str, float]) -> list[str]:
    return [
        key for key, threshold in THRESHOLDS.items() if metrics.get(key) != threshold
    ]


def run_fresh_clone_smoke(
    *,
    root: Path = Path("."),
    clone_dir: Path | None = None,
    runner: Runner = _run_subprocess,
    timeout: int = 900,
    keep_clone: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    env = _offline_env()
    started = time.monotonic()

    git_sha_result = runner(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        env=env,
        timeout=timeout,
    )
    git_sha = git_sha_result.stdout.strip() if git_sha_result.returncode == 0 else ""

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if clone_dir is None:
        temp_dir = tempfile.TemporaryDirectory(prefix="rfp-fresh-clone-")
        clone_dir = Path(temp_dir.name) / "repo"
    else:
        clone_dir = clone_dir.resolve()
        if clone_dir.exists() and not keep_clone:
            shutil.rmtree(clone_dir)

    checks: list[dict[str, Any]] = []
    metrics = {
        "git_sha_recorded": 1.0 if git_sha else 0.0,
        "no_credentials_required": (
            1.0 if all(key not in env for key in FORBIDDEN_PROVIDER_ENV) else 0.0
        ),
    }

    try:
        for spec in _command_specs(clone_dir):
            command_id = str(spec["id"])
            cmd = [
                git_sha if token == "{git_sha}" else token
                for token in list(spec["cmd"])
            ]
            cwd = root if spec["cwd"] is None else Path(spec["cwd"])
            result = runner(cmd, cwd=cwd, env=env, timeout=timeout)
            ok = result.returncode == 0
            metrics[_metric_name(command_id)] = 1.0 if ok else 0.0
            checks.append(
                {
                    "id": command_id,
                    "ok": ok,
                    "cmd": " ".join(cmd),
                    "cwd": str(cwd),
                    "returncode": result.returncode,
                    "stdout_tail": _compact_output(result.stdout),
                    "stderr_tail": _compact_output(result.stderr),
                }
            )
            if not ok:
                break
    finally:
        if temp_dir is not None and not keep_clone:
            temp_dir.cleanup()

    failed = _evaluate_thresholds(metrics)
    failed.extend(check["id"] for check in checks if not check["ok"])
    failed = sorted(set(failed))

    return {
        "fresh_clone_offline_smoke_complete": not failed,
        "stage5_schema_version": "fresh-clone-smoke-v1",
        "offline_only": True,
        "git_sha": git_sha,
        "clone_dir": str(clone_dir),
        "required_command": "uv run python -m rfp_rag.fresh_clone_smoke",
        "provider_env_forbidden": FORBIDDEN_PROVIDER_ENV,
        "metrics": metrics,
        "thresholds": THRESHOLDS,
        "checks": checks,
        "failed": failed,
        "run_ms": round((time.monotonic() - started) * 1000, 3),
        "notes": [
            "Runs from a local git clone at HEAD, not from the working tree.",
            "Provider credential environment variables are removed for every command.",
            "Creates a synthetic CI-parity corpus before running credential-free tests.",
        ],
    }


def write_fresh_clone_smoke(
    *,
    root: Path = Path("."),
    out: Path | None = None,
    clone_dir: Path | None = None,
    timeout: int = 900,
    keep_clone: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    summary = run_fresh_clone_smoke(
        root=root,
        clone_dir=clone_dir,
        timeout=timeout,
        keep_clone=keep_clone,
    )
    _write_json(out or root / DEFAULT_OUT, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a fresh local clone can run credential-free RFP checks."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--clone-dir", type=Path)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--keep-clone", action="store_true")
    args = parser.parse_args(argv)

    summary = write_fresh_clone_smoke(
        root=args.root,
        out=args.out,
        clone_dir=args.clone_dir,
        timeout=args.timeout,
        keep_clone=args.keep_clone,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["fresh_clone_offline_smoke_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
