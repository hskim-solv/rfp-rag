from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ANSWER_ERROR_PREFIXES = (
    "generation_error:",
    "retrieval_error:",
    "rerank_error:",
    "judge_error:",
)


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def summarize_eval_artifacts(
    eval_dir: Path,
    *,
    input_cost_per_1k: float = 0.0,
    output_cost_per_1k: float = 0.0,
) -> dict[str, Any]:
    metrics = _read_json(eval_dir / "metrics.json")
    predictions = _read_jsonl(eval_dir / "predictions.jsonl")
    estimated_input_tokens = 0
    estimated_output_tokens = 0
    warning_count = 0
    answer_error_count = 0

    for prediction in predictions:
        question = str(prediction.get("query") or "")
        contexts = "\n".join(str(text) for text in prediction.get("source_texts") or [])
        answer = str(prediction.get("answer") or "")
        estimated_input_tokens += estimate_tokens(question) + estimate_tokens(contexts)
        estimated_output_tokens += estimate_tokens(answer)
        warning_count += len(prediction.get("warnings") or [])
        if answer.startswith(ANSWER_ERROR_PREFIXES):
            answer_error_count += 1

    estimated_cost_usd = (
        estimated_input_tokens / 1000 * input_cost_per_1k
        + estimated_output_tokens / 1000 * output_cost_per_1k
    )

    return {
        "eval_dir": str(eval_dir),
        "provider_lane": metrics.get("provider_lane"),
        "gate": metrics.get("gate") or {},
        "aggregate": metrics.get("aggregate") or {},
        "prediction_count": len(predictions),
        "warning_count": warning_count,
        "answer_error_count": answer_error_count,
        "estimated_input_tokens": estimated_input_tokens,
        "estimated_output_tokens": estimated_output_tokens,
        "estimated_total_tokens": estimated_input_tokens + estimated_output_tokens,
        "estimated_cost_usd": round(estimated_cost_usd, 6),
    }


def summarize_audit_log(audit_path: Path) -> dict[str, Any]:
    rows = _read_jsonl(audit_path)
    by_tool: dict[str, dict[str, int]] = {}

    for row in rows:
        tool = str(row.get("tool") or "unknown")
        bucket = by_tool.setdefault(
            tool, {"total": 0, "success": 0, "failure": 0, "rejected": 0}
        )
        outcome = str(row.get("outcome") or "")
        bucket["total"] += 1
        if row.get("approved") is False or outcome == "rejected":
            bucket["rejected"] += 1
        elif "error" in outcome.casefold():
            bucket["failure"] += 1
        else:
            bucket["success"] += 1

    return {
        "audit_path": str(audit_path),
        "total_calls": len(rows),
        "by_tool": by_tool,
    }
