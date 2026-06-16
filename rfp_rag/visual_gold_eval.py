from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

VISUAL_CANDIDATE_DEFAULT_THRESHOLDS = {
    "min_precision": 0.70,
    "min_recall": 0.70,
    "min_f1": 0.70,
    "max_negative_violation_count": 3,
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"jsonl file not found: {path}")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"jsonl row must be an object on {path}:{line_number}")
            rows.append(row)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _fact_key(fact: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(fact.get("record_id") or "").strip(),
        str(fact.get("fact_type") or "").strip(),
        str(fact.get("field") or "").strip(),
    )


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 8)


def evaluate_visual_gold_candidates(
    gold_facts: Iterable[dict[str, Any]],
    candidate_facts: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    gold_rows = list(gold_facts)
    candidate_rows = list(candidate_facts)
    positive_keys = {
        _fact_key(fact) for fact in gold_rows if fact.get("status") == "accepted"
    }
    negative_keys = {
        _fact_key(fact) for fact in gold_rows if fact.get("status") == "rejected"
    }
    candidate_keys = {_fact_key(fact) for fact in candidate_rows}

    true_positive_keys = candidate_keys & positive_keys
    false_negative_keys = positive_keys - candidate_keys
    false_positive_keys = candidate_keys - positive_keys
    negative_violation_keys = candidate_keys & negative_keys
    unknown_candidate_keys = candidate_keys - positive_keys - negative_keys

    true_positive_count = len(true_positive_keys)
    false_positive_count = len(false_positive_keys)
    false_negative_count = len(false_negative_keys)
    precision = _ratio(true_positive_count, true_positive_count + false_positive_count)
    recall = _ratio(true_positive_count, true_positive_count + false_negative_count)
    f1_denominator = (
        (2 * true_positive_count) + false_positive_count + false_negative_count
    )
    f1 = _ratio(2 * true_positive_count, f1_denominator)

    return {
        "decision": "visual_gold_candidate_eval",
        "positive_gold_count": len(positive_keys),
        "negative_gold_count": len(negative_keys),
        "candidate_fact_count": len(candidate_keys),
        "true_positive_count": true_positive_count,
        "false_positive_count": false_positive_count,
        "false_negative_count": false_negative_count,
        "negative_violation_count": len(negative_violation_keys),
        "unknown_candidate_count": len(unknown_candidate_keys),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def check_visual_candidate_summary(
    summary: dict[str, Any],
    *,
    min_precision: float = VISUAL_CANDIDATE_DEFAULT_THRESHOLDS["min_precision"],
    min_recall: float = VISUAL_CANDIDATE_DEFAULT_THRESHOLDS["min_recall"],
    min_f1: float = VISUAL_CANDIDATE_DEFAULT_THRESHOLDS["min_f1"],
    max_negative_violation_count: int = VISUAL_CANDIDATE_DEFAULT_THRESHOLDS[
        "max_negative_violation_count"
    ],
) -> dict[str, Any]:
    thresholds = {
        "min_precision": min_precision,
        "min_recall": min_recall,
        "min_f1": min_f1,
        "max_negative_violation_count": max_negative_violation_count,
    }
    checks = [
        ("precision", float(summary.get("precision") or 0.0), min_precision, ">="),
        ("recall", float(summary.get("recall") or 0.0), min_recall, ">="),
        ("f1", float(summary.get("f1") or 0.0), min_f1, ">="),
        (
            "negative_violation_count",
            int(summary.get("negative_violation_count") or 0),
            max_negative_violation_count,
            "<=",
        ),
    ]
    failures = []
    for metric, actual, threshold, comparator in checks:
        passed = actual >= threshold if comparator == ">=" else actual <= threshold
        if not passed:
            failures.append(
                {
                    "metric": metric,
                    "actual": actual,
                    "threshold": threshold,
                    "comparator": comparator,
                }
            )
    return {
        "decision": "visual_candidate_gate",
        "ok": not failures,
        "thresholds": thresholds,
        "metrics": {
            "candidate_fact_count": int(summary.get("candidate_fact_count") or 0),
            "true_positive_count": int(summary.get("true_positive_count") or 0),
            "false_positive_count": int(summary.get("false_positive_count") or 0),
            "false_negative_count": int(summary.get("false_negative_count") or 0),
            "negative_violation_count": int(
                summary.get("negative_violation_count") or 0
            ),
            "unknown_candidate_count": int(summary.get("unknown_candidate_count") or 0),
            "precision": float(summary.get("precision") or 0.0),
            "recall": float(summary.get("recall") or 0.0),
            "f1": float(summary.get("f1") or 0.0),
        },
        "failures": failures,
    }


def run_visual_gold_eval(
    gold_path: Path | str,
    candidate_path: Path | str,
    out_dir: Path | str,
) -> dict[str, Any]:
    result = evaluate_visual_gold_candidates(
        _read_jsonl(Path(gold_path)),
        _read_jsonl(Path(candidate_path)),
    )
    _write_json(Path(out_dir) / "summary.json", result)
    return result
