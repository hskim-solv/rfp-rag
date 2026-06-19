from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_visual_quality(
    *, root: Path = Path("."), out: Path | None = None
) -> dict[str, Any]:
    root = root.resolve()
    out = out or root / "artifacts/visual_quality/summary.json"
    eval_metrics_path = root / "artifacts/eval/metrics.json"
    visual_eval_path = (
        root / "artifacts/visual_tesseract_candidate_expanded_eval/summary.json"
    )
    sidecar_regression_path = root / "artifacts/visual_quality/sidecar_regression.json"
    stage2_visual_questions_path = (
        root / "artifacts/eval_stage2/visual_table_questions.jsonl"
    )
    eval_metrics = _read_json(eval_metrics_path)
    visual_eval = _read_json(visual_eval_path)
    sidecar = _read_json(sidecar_regression_path)

    visual_count = _count_jsonl(stage2_visual_questions_path)
    if visual_count == 0:
        visual_count = (eval_metrics.get("query_set_counts") or {}).get(
            "visual_table", 0
        )
    hit_rate = (eval_metrics.get("aggregate") or {}).get(
        "visual_evidence_hit_rate", 0.0
    )
    negative_gold_count = visual_eval.get("negative_gold_count", 0)
    negative_violation_count = visual_eval.get("negative_violation_count", 0)
    unsupported_rate = 1.0
    if isinstance(negative_gold_count, int | float) and negative_gold_count > 0:
        unsupported_rate = negative_violation_count / negative_gold_count
    metrics = {
        "visual_question_count": visual_count,
        "visual_evidence_hit_rate": hit_rate,
        "unsupported_visual_claim_rate": unsupported_rate,
        "sidecar_citation_no_regression": 1.0
        if sidecar.get("sidecar_citation_no_regression") is True
        else 0.0,
        "sidecar_abstention_no_regression": 1.0
        if sidecar.get("sidecar_abstention_no_regression") is True
        else 0.0,
    }
    thresholds = {
        "visual_question_count": 30,
        "visual_evidence_hit_rate": 0.90,
        "unsupported_visual_claim_rate": 0.10,
        "sidecar_citation_no_regression": 1.0,
        "sidecar_abstention_no_regression": 1.0,
    }
    failed: list[str] = []
    if metrics["visual_question_count"] < thresholds["visual_question_count"]:
        failed.append("visual_question_count")
    if metrics["visual_evidence_hit_rate"] < thresholds["visual_evidence_hit_rate"]:
        failed.append("visual_evidence_hit_rate")
    if (
        metrics["unsupported_visual_claim_rate"]
        > thresholds["unsupported_visual_claim_rate"]
    ):
        failed.append("unsupported_visual_claim_rate")
    for key in ("sidecar_citation_no_regression", "sidecar_abstention_no_regression"):
        if metrics[key] != thresholds[key]:
            failed.append(key)

    summary = {
        "visual_quality_complete": not failed,
        "metrics": metrics,
        "thresholds": thresholds,
        "failed": sorted(failed),
        "measured_sources": [
            str(path.relative_to(root))
            for path in (
                eval_metrics_path,
                stage2_visual_questions_path,
                visual_eval_path,
                sidecar_regression_path,
            )
            if path.exists()
        ],
    }
    _write_json(out, summary)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write Stage 2 visual-quality evidence summary."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    summary = write_visual_quality(root=args.root, out=args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["visual_quality_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
