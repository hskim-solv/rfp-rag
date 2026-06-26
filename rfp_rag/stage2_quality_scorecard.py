from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


DEFAULT_OUT = Path("artifacts/stage2_quality_scorecard/summary.json")

THRESHOLDS = {
    "parser_doc_count": 100,
    "parser_average_quality_score": 0.90,
    "parser_page_citation_coverage": 1.0,
    "parser_low_quality_doc_count": 0,
    "stage2_query_count": 150,
    "stage3_query_count": 100,
    "context_precision_at5": 0.70,
    "context_recall_at5": 0.75,
    "citation_precision_proxy": 0.90,
    "unsupported_claim_rate": 0.03,
    "stage3_recall_at5": 0.90,
    "stage3_mrr": 0.80,
    "stage3_faithfulness": 0.85,
    "stage3_answer_relevancy": 0.85,
    "retrieval_no_regression": 1.0,
    "visual_evidence_hit_rate": 0.90,
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _float(value: Any, default: float = 0.0) -> float:
    return float(value) if isinstance(value, int | float) else default


def _count_stage2_queries(stage2: dict[str, Any]) -> int:
    counts = stage2.get("query_set_counts") or {}
    total = counts.get("total")
    if isinstance(total, int):
        return total
    metrics = stage2.get("metrics") or {}
    return int(_float(metrics.get("query_count"), 0.0))


def _prediction_context_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    precision_values: list[float] = []
    recall_values: list[float] = []
    citation_values: list[float] = []

    for row in rows:
        expected = {str(doc_id) for doc_id in row.get("expected_doc_ids") or []}
        if not expected:
            continue
        retrieved = [str(doc_id) for doc_id in row.get("retrieved_doc_ids") or []]
        if retrieved:
            relevant_retrieved = [doc_id for doc_id in retrieved if doc_id in expected]
            precision_values.append(len(relevant_retrieved) / len(retrieved))
            recall_values.append(len(set(retrieved) & expected) / len(expected))
        citation_validity = (row.get("pass_fail") or {}).get("citation_validity")
        if isinstance(citation_validity, int | float):
            citation_values.append(float(citation_validity))

    return {
        "answerable_prediction_count": float(len(precision_values)),
        "context_precision_at5": mean(precision_values) if precision_values else 0.0,
        "context_recall_at5": mean(recall_values) if recall_values else 0.0,
        "citation_precision_proxy": mean(citation_values) if citation_values else 0.0,
    }


def _all_equal(
    metrics: dict[str, Any], keys: tuple[str, ...], expected: float
) -> float:
    return 1.0 if all(_float(metrics.get(key)) == expected for key in keys) else 0.0


def _evaluate_thresholds(metrics: dict[str, float]) -> list[str]:
    failed: list[str] = []
    for key, threshold in THRESHOLDS.items():
        value = metrics.get(key)
        if value is None:
            failed.append(key)
            continue
        if key in {"parser_low_quality_doc_count", "unsupported_claim_rate"}:
            if value > threshold:
                failed.append(key)
        elif value < threshold:
            failed.append(key)
    return failed


def build_stage2_quality_scorecard(*, root: Path = Path(".")) -> dict[str, Any]:
    root = root.resolve()
    paths = {
        "parser_quality": root / "artifacts/parser_quality/summary.json",
        "retrieval_bakeoff": root / "artifacts/retrieval_bakeoff/summary.json",
        "visual_quality": root / "artifacts/visual_quality/summary.json",
        "stage2_real": root / "artifacts/eval_stage2_real/metrics.json",
        "stage3_holdout": root / "artifacts/eval_stage3_holdout/metrics.json",
        "stage3_predictions": root / "artifacts/eval_stage3_raw/predictions.jsonl",
    }
    missing = [
        name
        for name, path in paths.items()
        if not path.exists() or (path.is_file() and path.stat().st_size == 0)
    ]

    parser = _read_json(paths["parser_quality"])
    retrieval = _read_json(paths["retrieval_bakeoff"])
    visual = _read_json(paths["visual_quality"])
    stage2 = _read_json(paths["stage2_real"])
    stage3 = _read_json(paths["stage3_holdout"])
    stage3_metrics = stage3.get("metrics") or {}
    prediction_metrics = _prediction_context_metrics(
        _read_jsonl(paths["stage3_predictions"])
    )
    retrieval_metrics = retrieval.get("metrics") or {}
    visual_metrics = visual.get("metrics") or {}

    metrics = {
        "parser_doc_count": _float(parser.get("doc_count")),
        "parser_average_quality_score": _float(parser.get("average_quality_score")),
        "parser_page_citation_coverage": _float(parser.get("page_citation_coverage")),
        "parser_low_quality_doc_count": _float(parser.get("low_quality_doc_count")),
        "stage2_query_count": float(_count_stage2_queries(stage2)),
        "stage3_query_count": _float(stage3_metrics.get("query_count")),
        "stage3_document_count": _float(stage3_metrics.get("document_count")),
        "context_precision_at5": prediction_metrics["context_precision_at5"],
        "context_recall_at5": prediction_metrics["context_recall_at5"],
        "citation_precision_proxy": prediction_metrics["citation_precision_proxy"],
        "answerable_prediction_count": prediction_metrics[
            "answerable_prediction_count"
        ],
        "unsupported_claim_rate": _float(
            stage3_metrics.get("unsupported_visual_claim_rate")
        ),
        "stage3_recall_at5": _float(stage3_metrics.get("recall@5")),
        "stage3_mrr": _float(stage3_metrics.get("mrr")),
        "stage3_faithfulness": _float(stage3_metrics.get("faithfulness")),
        "stage3_answer_relevancy": _float(stage3_metrics.get("answer_relevancy")),
        "retrieval_no_regression": _all_equal(
            retrieval_metrics,
            (
                "recall_no_regression",
                "citation_validity_no_regression",
                "abstention_no_regression",
                "section_hit_no_regression",
                "visual_evidence_no_regression",
                "latency_budget_pass",
                "cost_budget_pass",
            ),
            1.0,
        ),
        "visual_evidence_hit_rate": _float(
            visual_metrics.get("visual_evidence_hit_rate")
        ),
        "visual_question_count": _float(visual_metrics.get("visual_question_count")),
    }

    failed = [f"missing:{name}" for name in missing]
    failed.extend(_evaluate_thresholds(metrics))
    if not retrieval.get("retrieval_bakeoff_complete"):
        failed.append("retrieval_bakeoff_complete")
    if not visual.get("visual_quality_complete"):
        failed.append("visual_quality_complete")
    if not stage2.get("holdout_quality_complete"):
        failed.append("stage2_holdout_quality_complete")
    if not stage3.get("stage3_holdout_quality_complete"):
        failed.append("stage3_holdout_quality_complete")

    return {
        "stage2_quality_scorecard_complete": not failed,
        "metrics": metrics,
        "thresholds": THRESHOLDS,
        "failed": sorted(set(failed)),
        "evidence_paths": {
            key: str(path.relative_to(root)) for key, path in paths.items()
        },
        "method": {
            "context_precision_at5": (
                "mean fraction of retrieved_doc_ids whose doc_id is expected, "
                "over answerable Stage 3 predictions"
            ),
            "context_recall_at5": (
                "mean fraction of expected_doc_ids retrieved at least once, "
                "over answerable Stage 3 predictions"
            ),
            "citation_precision_proxy": (
                "mean pass_fail.citation_validity over answerable Stage 3 predictions; "
                "used because ragas was intentionally removed"
            ),
        },
        "notes": [
            "This scorecard is deterministic and credential-free.",
            "It does not claim unseen-document public-traffic performance.",
            "It aggregates existing parser, retrieval, visual, Stage 2, and Stage 3 evidence.",
        ],
    }


def write_stage2_quality_scorecard(
    *, root: Path = Path("."), out: Path | None = None
) -> dict[str, Any]:
    root = root.resolve()
    summary = build_stage2_quality_scorecard(root=root)
    out = out or root / DEFAULT_OUT
    _write_json(out, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate Stage 2 RAG/parser quality evidence into a senior portfolio scorecard."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    summary = write_stage2_quality_scorecard(root=args.root, out=args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["stage2_quality_scorecard_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
