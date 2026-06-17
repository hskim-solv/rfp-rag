from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rfp_rag.guardrails import check_question_guardrails


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _round(value: float) -> float:
    return round(value, 6)


def evaluate_guardrail_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    scored: list[dict[str, Any]] = []
    block_total = 0
    block_passed = 0
    allow_total = 0
    allow_passed = 0
    category_passed = 0

    for case in cases:
        result = check_question_guardrails(str(case["question"]))
        expected_allowed = bool(case["expected_allowed"])
        expected_categories = list(case.get("expected_categories") or [])
        actual_categories = result.categories
        allowed_ok = result.allowed == expected_allowed
        category_ok = sorted(actual_categories) == sorted(expected_categories)
        passed = allowed_ok and category_ok

        if expected_allowed:
            allow_total += 1
            allow_passed += int(allowed_ok)
        else:
            block_total += 1
            block_passed += int(not result.allowed)
        category_passed += int(category_ok)

        scored.append(
            {
                "id": case.get("id"),
                "question": case.get("question"),
                "expected_allowed": expected_allowed,
                "actual_allowed": result.allowed,
                "expected_categories": expected_categories,
                "actual_categories": actual_categories,
                "reasons": result.reasons,
                "passed": passed,
            }
        )

    passed_count = sum(1 for row in scored if row["passed"])
    case_count = len(scored)
    metrics = {
        "block_recall": _round(block_passed / block_total) if block_total else 1.0,
        "allow_recall": _round(allow_passed / allow_total) if allow_total else 1.0,
        "category_exact_match": _round(category_passed / case_count)
        if case_count
        else 1.0,
    }

    return {
        "guardrail_regression_complete": passed_count == case_count,
        "case_count": case_count,
        "passed": passed_count,
        "failed": case_count - passed_count,
        "metrics": metrics,
        "cases": scored,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic prompt-injection/secrets guardrail regression."
    )
    parser.add_argument(
        "--cases", type=Path, default=Path("tests/fixtures/guardrail_cases.jsonl")
    )
    parser.add_argument(
        "--out", type=Path, default=Path("artifacts/guardrails/summary.json")
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    report = evaluate_guardrail_cases(_read_jsonl(args.cases))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if report["guardrail_regression_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
