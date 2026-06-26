from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


THRESHOLDS = {
    "recall@5": 0.95,
    "recall@3": 0.90,
    "mrr": 0.85,
    "metadata_exact_match": 0.95,
    "faithfulness": 0.90,
    "answer_relevancy": 0.80,
    "judge_coverage_faithfulness_min_by_answerable_slice": 0.95,
    "judge_coverage_answer_relevancy_min_by_answerable_slice": 0.95,
    "citation_presence": 1.0,
    "citation_validity": 1.0,
}

STAGE2_CONTRACT_VERSION = "rfp-rag-stage2-real-v1"

LINEAGE_FIELDS = (
    "generation_model_id",
    "judge_model_id",
    "embedding_model_id",
    "prompt_template_hash",
)

QUERY_COUNT_KEY_MAP = {
    "metadata": "golden_metadata",
    "curated_text": "curated_text",
    "section_lookup": "section_lookup",
    "cross_document": "cross_document",
    "visual_table": "visual_table",
    "paraphrase": "paraphrase",
    "abstention": "abstention",
}

QUERY_ID_SLICE_MAP = {
    "metadata": "metadata",
    "curated": "curated_text",
    "section": "section_lookup",
    "cross": "cross_document",
    "visual": "visual_table",
    "paraphrase": "paraphrase",
    "abstention": "abstention",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _metric(raw: dict[str, Any], key: str) -> float | None:
    value = (raw.get("aggregate") or {}).get(key)
    if value is None:
        value = (raw.get("metrics") or {}).get(key)
    if isinstance(value, int | float):
        return float(value)
    return None


def _judge_coverage_min(raw: dict[str, Any], key: str) -> float | None:
    per_type = raw.get("per_type") or {}
    values = []
    for slice_metrics in per_type.values():
        if not isinstance(slice_metrics, dict):
            continue
        count = slice_metrics.get("count", 0)
        if not isinstance(count, int | float) or count <= 0:
            continue
        value = slice_metrics.get(key)
        if isinstance(value, int | float):
            values.append(float(value))
    if values:
        return min(values)
    stage2_key = f"{key}_min_by_answerable_slice"
    value = (raw.get("metrics") or {}).get(stage2_key)
    if isinstance(value, int | float):
        return float(value)
    return _metric(raw, key)


def _prediction_slice(row: dict[str, Any]) -> str | None:
    query_id = str(row.get("query_id") or "")
    prefix = query_id.split("_", 1)[0] if query_id else ""
    return QUERY_ID_SLICE_MAP.get(prefix)


def prediction_judge_coverage_summary(
    predictions_path: Path, coverage: dict[str, Any]
) -> dict[str, Any]:
    rows = _read_jsonl(predictions_path)
    if not rows:
        return {
            "ok": False,
            "path": str(predictions_path),
            "issues": ["predictions_missing"],
            "counts_by_slice": {},
            "faithfulness_by_slice": {},
            "answer_relevancy_by_slice": {},
            "faithfulness_min_by_answerable_slice": None,
            "answer_relevancy_min_by_answerable_slice": None,
        }

    counts: dict[str, int] = {}
    faithfulness_scored: dict[str, int] = {}
    relevancy_scored: dict[str, int] = {}
    issues: list[str] = []

    for row in rows:
        slice_name = _prediction_slice(row)
        if slice_name is None:
            issues.append("query_id_slice")
            continue
        counts[slice_name] = counts.get(slice_name, 0) + 1
        judge = row.get("judge") or {}
        if not isinstance(judge, dict):
            continue
        if isinstance(judge.get("faithfulness"), int | float):
            faithfulness_scored[slice_name] = faithfulness_scored.get(slice_name, 0) + 1
        if isinstance(judge.get("answer_relevancy"), int | float):
            relevancy_scored[slice_name] = relevancy_scored.get(slice_name, 0) + 1

    expected_counts = coverage.get("counts_by_slice") or {}
    if isinstance(expected_counts, dict):
        for slice_name, expected in expected_counts.items():
            if isinstance(expected, int | float) and counts.get(slice_name, 0) != int(
                expected
            ):
                issues.append(f"prediction_counts.{slice_name}")

    answerable_slices = sorted(
        slice_name
        for slice_name, count in counts.items()
        if slice_name != "abstention" and count > 0
    )
    faithfulness_by_slice = {
        slice_name: faithfulness_scored.get(slice_name, 0) / counts[slice_name]
        for slice_name in answerable_slices
    }
    relevancy_by_slice = {
        slice_name: relevancy_scored.get(slice_name, 0) / counts[slice_name]
        for slice_name in answerable_slices
    }
    faithfulness_min = (
        min(faithfulness_by_slice.values()) if faithfulness_by_slice else None
    )
    relevancy_min = min(relevancy_by_slice.values()) if relevancy_by_slice else None
    threshold_faithfulness = THRESHOLDS[
        "judge_coverage_faithfulness_min_by_answerable_slice"
    ]
    threshold_relevancy = THRESHOLDS[
        "judge_coverage_answer_relevancy_min_by_answerable_slice"
    ]
    if faithfulness_min is None or faithfulness_min < threshold_faithfulness:
        issues.append("prediction_judge_coverage_faithfulness")
    if relevancy_min is None or relevancy_min < threshold_relevancy:
        issues.append("prediction_judge_coverage_answer_relevancy")

    return {
        "ok": not issues,
        "path": str(predictions_path),
        "issues": sorted(set(issues)),
        "counts_by_slice": dict(sorted(counts.items())),
        "faithfulness_by_slice": faithfulness_by_slice,
        "answer_relevancy_by_slice": relevancy_by_slice,
        "faithfulness_min_by_answerable_slice": faithfulness_min,
        "answer_relevancy_min_by_answerable_slice": relevancy_min,
    }


def _stage2_metrics(raw: dict[str, Any]) -> dict[str, float | None]:
    return {
        "recall@5": _metric(raw, "recall@5"),
        "recall@3": _metric(raw, "recall@3"),
        "mrr": _metric(raw, "mrr"),
        "metadata_exact_match": _metric(raw, "metadata_exact_match"),
        "faithfulness": _metric(raw, "faithfulness"),
        "answer_relevancy": _metric(raw, "answer_relevancy"),
        "judge_coverage_faithfulness_min_by_answerable_slice": _judge_coverage_min(
            raw, "judge_coverage_faithfulness"
        ),
        "judge_coverage_answer_relevancy_min_by_answerable_slice": _judge_coverage_min(
            raw, "judge_coverage_answer_relevancy"
        ),
        "citation_presence": _metric(raw, "citation_presence"),
        "citation_validity": _metric(raw, "citation_validity"),
    }


def _passing_metrics(metrics: dict[str, float | None]) -> list[str]:
    failed = []
    for key, threshold in THRESHOLDS.items():
        value = metrics.get(key)
        if value is None or value < threshold:
            failed.append(key)
    return failed


def _query_set_failures(raw: dict[str, Any], coverage: dict[str, Any]) -> list[str]:
    raw_hash = raw.get("eval_set_hash")
    coverage_hash = coverage.get("eval_set_hash")
    failures: list[str] = []
    if raw_hash is not None and raw_hash != coverage_hash:
        failures.append("eval_set_hash")

    raw_counts = raw.get("query_set_counts") or {}
    coverage_counts = coverage.get("counts_by_slice") or {}
    if not isinstance(raw_counts, dict) or not isinstance(coverage_counts, dict):
        return ["query_set_counts"]
    expected_total = sum(
        int(value)
        for value in coverage_counts.values()
        if isinstance(value, int | float)
    )
    if raw_counts.get("total") != expected_total:
        failures.append("query_set_counts.total")
    for coverage_key, raw_key in QUERY_COUNT_KEY_MAP.items():
        if coverage_key in coverage_counts and raw_counts.get(
            raw_key
        ) != coverage_counts.get(coverage_key):
            failures.append(f"query_set_counts.{raw_key}")
    return failures


def finalize_stage2_real(
    *,
    root: Path = Path("."),
    metrics_path: Path | None = None,
    coverage_path: Path | None = None,
    predictions_path: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    metrics_path = metrics_path or root / "artifacts/eval_stage2_real/metrics.json"
    coverage_path = coverage_path or root / "artifacts/eval_stage2/coverage.json"
    predictions_path = predictions_path or metrics_path.parent / "predictions.jsonl"
    raw = _read_json(metrics_path)
    coverage = _read_json(coverage_path)

    metrics = _stage2_metrics(raw)
    prediction_coverage = prediction_judge_coverage_summary(predictions_path, coverage)
    if prediction_coverage["faithfulness_min_by_answerable_slice"] is not None:
        metrics["judge_coverage_faithfulness_min_by_answerable_slice"] = float(
            prediction_coverage["faithfulness_min_by_answerable_slice"]
        )
    if prediction_coverage["answer_relevancy_min_by_answerable_slice"] is not None:
        metrics["judge_coverage_answer_relevancy_min_by_answerable_slice"] = float(
            prediction_coverage["answer_relevancy_min_by_answerable_slice"]
        )
    metric_failures = _passing_metrics(metrics)
    query_set_failures = _query_set_failures(raw, coverage)
    prediction_failures = list(prediction_coverage["issues"])
    lineage_failures = [field for field in LINEAGE_FIELDS if not raw.get(field)]
    if (
        not isinstance(raw.get("prompt_template_hash"), str)
        or len(str(raw.get("prompt_template_hash", ""))) != 64
    ):
        lineage_failures.append("prompt_template_hash")
    if raw.get("provider_lane") != "real_openai":
        lineage_failures.append("provider_lane")
    evaluation_valid = raw.get("evaluation_valid", raw.get("holdout_quality_complete"))
    if evaluation_valid is not True:
        lineage_failures.append("evaluation_valid")

    failed = sorted(
        set(
            metric_failures
            + lineage_failures
            + query_set_failures
            + prediction_failures
        )
    )
    thresholds_met = not metric_failures
    summary = {
        "holdout_quality_complete": not failed,
        "contract_version": STAGE2_CONTRACT_VERSION,
        "eval_set_hash": coverage.get("eval_set_hash", ""),
        "source_eval_set_hash": raw.get("eval_set_hash", ""),
        "required_command": (
            "python3 -m rfp_rag.evaluate --data data/data_list.csv "
            "--index artifacts/index_real --out artifacts/eval_stage2_real "
            "--provider real_openai --top-k 5 --min-score 0.47 "
            "--visual-records artifacts/visual_structure_reviewed/records.jsonl"
        ),
        "thresholds_met": thresholds_met,
        "per_slice_failed": sorted(metric_failures),
        "generation_model_id": raw.get("generation_model_id", ""),
        "judge_model_id": raw.get("judge_model_id", ""),
        "embedding_model_id": raw.get("embedding_model_id", ""),
        "prompt_template_hash": raw.get("prompt_template_hash", ""),
        "provider_lane": raw.get("provider_lane", ""),
        "evaluation_valid": evaluation_valid is True,
        "query_set_counts": raw.get("query_set_counts", {}),
        "prediction_judge_coverage": prediction_coverage,
        "metrics": metrics,
        "thresholds": dict(THRESHOLDS),
        "failed": failed,
        "source_metrics_path": str(metrics_path.relative_to(root))
        if metrics_path.is_relative_to(root)
        else str(metrics_path),
    }
    _write_json(metrics_path, summary)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Finalize Stage 2 real holdout metrics into the portfolio contract."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--metrics", type=Path, default=None)
    parser.add_argument("--coverage", type=Path, default=None)
    parser.add_argument("--predictions", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    summary = finalize_stage2_real(
        root=args.root,
        metrics_path=args.metrics,
        coverage_path=args.coverage,
        predictions_path=args.predictions,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["holdout_quality_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
