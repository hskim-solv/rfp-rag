#!/usr/bin/env python3
"""Block direct edits to committed-secret style env files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import PurePosixPath


ALLOW_NAMES = {".env.example", ".env.sample", ".env.template"}


def is_blocked_env(path: str) -> bool:
    normalized = path.replace("\\", "/")
    name = PurePosixPath(normalized).name
    if name in ALLOW_NAMES:
        return False
    return name == ".env" or name.startswith(".env.")


def walk(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).lower()
            if isinstance(value, str) and ("path" in key_l or "file" in key_l):
                yield value
            yield from walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk(value)


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from strings(value)


def patch_paths(text: str):
    patterns = [
        r"^\*\*\* (?:Update|Add|Delete) File: (.+)$",
        r"^[+-]{3} [ab]/(.+)$",
    ]
    for line in text.splitlines():
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                yield match.group(1).strip()


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    candidates = set(walk(payload))
    for value in strings(payload):
        candidates.update(patch_paths(value))
    candidates.update(patch_paths(raw))

    blocked = sorted(path for path in candidates if is_blocked_env(path))
    if blocked:
        print(
            "BLOCKED: direct edits to .env files are not allowed. "
            "Update .env.example/.env.sample/.env.template instead.",
            file=sys.stderr,
        )
        for path in blocked:
            print(f"- {path}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
