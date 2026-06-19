from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED_MODES = ("vector", "bm25", "hybrid_rrf")
OPTIONAL_DEFERRED_MODES = {
    "reranker": {
        "status": "deferred",
        "reason": (
            "LLM reranker remains optional until a same-set paid/API artifact "
            "exists; OpenAI real reranker is currently blocked by insufficient_quota "
            "and the open reranker attempt used a non-comparable query set."
        ),
        "reconsider_when": (
            "a real_openai or open run with reranker='llm' shares the bakeoff "
            "query_set_hash and beats vector without quality, latency, or cost regression"
        ),
    }
}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_payload(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _metric(run: dict[str, Any], name: str, default: float = 0.0) -> float:
    value = (run.get("metrics") or {}).get(name, default)
    return float(value) if isinstance(value, int | float) else default


def compare_retrieval_runs(
    *,
    baseline: dict[str, Any],
    candidates: list[dict[str, Any]],
    max_latency_ratio: float = 1.25,
    max_cost_ratio: float = 1.25,
) -> dict[str, Any]:
    all_runs = [baseline, *candidates]
    comparison_hashes = {str(run.get("query_set_hash") or "") for run in all_runs}
    failed: list[str] = []
    if len(comparison_hashes) != 1 or "" in comparison_hashes:
        failed.append("comparison_set_hash")
    best_candidate = max(
        candidates, key=lambda run: _metric(run, "recall@5"), default=None
    )
    if best_candidate is None:
        failed.append("missing_candidates")
    non_regressing_candidates = []
    for candidate in candidates:
        if (
            _metric(candidate, "recall@5") >= _metric(baseline, "recall@5")
            and _metric(candidate, "citation_validity")
            >= _metric(baseline, "citation_validity")
            and _metric(candidate, "abstention_pass")
            >= _metric(baseline, "abstention_pass")
            and _metric(candidate, "section_hit_rate")
            >= _metric(baseline, "section_hit_rate")
            and _metric(candidate, "visual_evidence_hit_rate")
            >= _metric(baseline, "visual_evidence_hit_rate")
        ):
            non_regressing_candidates.append(candidate)
    candidate = max(
        non_regressing_candidates,
        key=lambda run: _metric(run, "recall@5"),
        default=baseline,
    )

    recall_ok = _metric(candidate, "recall@5") >= _metric(baseline, "recall@5")
    citation_ok = _metric(candidate, "citation_validity") >= _metric(
        baseline, "citation_validity"
    )
    abstention_ok = _metric(candidate, "abstention_pass") >= _metric(
        baseline, "abstention_pass"
    )
    section_ok = _metric(candidate, "section_hit_rate") >= _metric(
        baseline, "section_hit_rate"
    )
    visual_ok = _metric(candidate, "visual_evidence_hit_rate") >= _metric(
        baseline, "visual_evidence_hit_rate"
    )
    base_latency = max(_metric(baseline, "latency_p95_ms", 1.0), 1.0)
    base_cost = max(_metric(baseline, "estimated_cost_usd", 0.000001), 0.000001)
    latency_ok = _metric(candidate, "latency_p95_ms", base_latency) <= (
        base_latency * max_latency_ratio
    )
    cost_ok = _metric(candidate, "estimated_cost_usd", base_cost) <= (
        base_cost * max_cost_ratio
    )
    metrics = {
        "recall_no_regression": 1.0 if recall_ok else 0.0,
        "citation_validity_no_regression": 1.0 if citation_ok else 0.0,
        "abstention_no_regression": 1.0 if abstention_ok else 0.0,
        "section_hit_no_regression": 1.0 if section_ok else 0.0,
        "visual_evidence_no_regression": 1.0 if visual_ok else 0.0,
        "latency_budget_pass": 1.0 if latency_ok else 0.0,
        "cost_budget_pass": 1.0 if cost_ok else 0.0,
    }
    thresholds = {
        "recall_no_regression": 1.0,
        "citation_validity_no_regression": 1.0,
        "abstention_no_regression": 1.0,
        "section_hit_no_regression": 1.0,
        "visual_evidence_no_regression": 1.0,
        "latency_budget_pass": 1.0,
        "cost_budget_pass": 1.0,
    }
    failed.extend(
        key for key, threshold in thresholds.items() if metrics[key] != threshold
    )
    decision = "keep_vector_until_candidate_wins"
    if not failed and candidate.get("name") != baseline.get("name"):
        decision = f"adopt_{candidate['name']}"
    return {
        "retrieval_bakeoff_complete": not failed,
        "decision": decision,
        "comparison_set_hash": next(iter(comparison_hashes))
        if len(comparison_hashes) == 1
        else "",
        "compared_modes": [str(run.get("name")) for run in all_runs],
        "decision_adr_path": "docs/adr/0020-retrieval-bakeoff.md",
        "metrics": metrics,
        "thresholds": thresholds,
        "failed": sorted(set(failed)),
        "runs": all_runs,
    }


def _run_from_metrics(
    name: str,
    path: Path,
    *,
    expected_reranker: str | None = None,
) -> dict[str, Any] | None:
    metrics = _read_json(path)
    if not metrics:
        return None
    if expected_reranker is not None and metrics.get("reranker") != expected_reranker:
        return None
    aggregate = metrics.get("aggregate") or {}
    query_counts = metrics.get("query_set_counts") or {}
    return {
        "name": name,
        "path": str(path),
        "query_set_hash": _hash_payload(query_counts),
        "metrics": {
            "recall@5": aggregate.get("recall@5", 0.0),
            "citation_validity": aggregate.get("citation_validity", 0.0),
            "abstention_pass": aggregate.get("abstention_pass", 0.0),
            "section_hit_rate": aggregate.get("section_hit_rate", 0.0),
            "visual_evidence_hit_rate": aggregate.get("visual_evidence_hit_rate", 0.0),
            "latency_p95_ms": metrics.get("latency_p95_ms", 0.0),
            "estimated_cost_usd": metrics.get("estimated_cost_usd", 0.0),
        },
    }


def _reranker_run(root: Path) -> dict[str, Any] | None:
    for path in (
        root / "artifacts/eval_open_rerank/metrics.json",
        root / "artifacts/eval_real_rerank/metrics.json",
    ):
        run = _run_from_metrics("reranker", path, expected_reranker="llm")
        if run is not None:
            return run
    return None


def write_retrieval_bakeoff(
    *, root: Path = Path("."), out: Path | None = None
) -> dict[str, Any]:
    root = root.resolve()
    out = out or root / "artifacts/retrieval_bakeoff/summary.json"
    baseline = _run_from_metrics("vector", root / "artifacts/eval/metrics.json")
    runs = {
        "vector": baseline,
        "hybrid_rrf": _run_from_metrics(
            "hybrid_rrf", root / "artifacts/eval_hybrid_offline/metrics.json"
        ),
        "reranker": _reranker_run(root),
        "bm25": _run_from_metrics(
            "bm25", root / "artifacts/eval_bm25_offline/metrics.json"
        ),
    }
    if baseline is None:
        summary = {
            "retrieval_bakeoff_complete": False,
            "decision": "missing_vector_baseline",
            "comparison_set_hash": "",
            "compared_modes": [],
            "decision_adr_path": "docs/adr/0020-retrieval-bakeoff.md",
            "metrics": {
                "recall_no_regression": 0.0,
                "citation_validity_no_regression": 0.0,
                "abstention_no_regression": 0.0,
                "section_hit_no_regression": 0.0,
                "visual_evidence_no_regression": 0.0,
                "latency_budget_pass": 0.0,
                "cost_budget_pass": 0.0,
            },
            "thresholds": {
                "recall_no_regression": 1.0,
                "citation_validity_no_regression": 1.0,
                "abstention_no_regression": 1.0,
                "section_hit_no_regression": 1.0,
                "visual_evidence_no_regression": 1.0,
                "latency_budget_pass": 1.0,
                "cost_budget_pass": 1.0,
            },
            "failed": ["missing_vector_baseline", "missing_modes"],
            "available_modes": [],
            "missing_modes": list(REQUIRED_MODES),
            "optional_deferred_modes": OPTIONAL_DEFERRED_MODES,
        }
        _write_json(out, summary)
        return summary

    available = [name for name, run in runs.items() if run is not None]
    candidates = [
        run for name, run in runs.items() if name != "vector" and run is not None
    ]
    summary = compare_retrieval_runs(baseline=baseline, candidates=candidates)
    missing = [mode for mode in REQUIRED_MODES if mode not in available]
    if missing:
        summary["retrieval_bakeoff_complete"] = False
        summary["failed"] = sorted(set([*summary["failed"], "missing_modes"]))
    summary["available_modes"] = available
    summary["missing_modes"] = missing
    summary["optional_deferred_modes"] = OPTIONAL_DEFERRED_MODES
    _write_json(out, summary)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare retrieval modes for Stage 2 bakeoff evidence."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    summary = write_retrieval_bakeoff(root=args.root, out=args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["retrieval_bakeoff_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
