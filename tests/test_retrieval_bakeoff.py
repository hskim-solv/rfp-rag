from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.retrieval_bakeoff import (
    compare_retrieval_runs,
    main,
    write_retrieval_bakeoff,
)


def _run(
    name: str,
    *,
    recall: float,
    citation: float = 1.0,
    abstention: float = 1.0,
    section: float = 1.0,
    visual: float = 1.0,
    latency_ms: float = 100.0,
    cost_usd: float = 0.01,
    query_hash: str = "same-set",
) -> dict:
    return {
        "name": name,
        "query_set_hash": query_hash,
        "metrics": {
            "recall@5": recall,
            "citation_validity": citation,
            "abstention_pass": abstention,
            "section_hit_rate": section,
            "visual_evidence_hit_rate": visual,
            "latency_p95_ms": latency_ms,
            "estimated_cost_usd": cost_usd,
        },
    }


def test_compare_retrieval_runs_selects_candidate_without_regressions() -> None:
    result = compare_retrieval_runs(
        baseline=_run("vector", recall=0.90),
        candidates=[_run("hybrid_rrf", recall=0.95)],
    )

    assert result["retrieval_bakeoff_complete"] is True
    assert result["decision"] == "adopt_hybrid_rrf"
    assert result["metrics"]["recall_no_regression"] == 1.0
    assert result["failed"] == []


def test_compare_retrieval_runs_rejects_mismatched_frozen_sets() -> None:
    result = compare_retrieval_runs(
        baseline=_run("vector", recall=0.90, query_hash="set-a"),
        candidates=[_run("hybrid_rrf", recall=0.95, query_hash="set-b")],
    )

    assert result["retrieval_bakeoff_complete"] is False
    assert "comparison_set_hash" in result["failed"]


def test_compare_retrieval_runs_keeps_vector_when_no_candidate_wins() -> None:
    result = compare_retrieval_runs(
        baseline=_run("vector", recall=0.95),
        candidates=[
            _run("bm25", recall=0.80),
            _run("hybrid_rrf", recall=0.90, section=0.8),
            _run("reranker", recall=0.92),
        ],
    )

    assert result["retrieval_bakeoff_complete"] is True
    assert result["decision"] == "keep_vector_until_candidate_wins"
    assert result["metrics"] == {
        "abstention_no_regression": 1.0,
        "citation_validity_no_regression": 1.0,
        "cost_budget_pass": 1.0,
        "latency_budget_pass": 1.0,
        "recall_no_regression": 1.0,
        "section_hit_no_regression": 1.0,
        "visual_evidence_no_regression": 1.0,
    }
    assert result["failed"] == []


def test_write_retrieval_bakeoff_records_current_artifact_gaps(tmp_path: Path) -> None:
    eval_dir = tmp_path / "artifacts/eval"
    eval_dir.mkdir(parents=True)
    (eval_dir / "metrics.json").write_text(
        json.dumps(
            {
                "retrieval_mode": "vector",
                "reranker": "none",
                "query_set_counts": {"total": 10},
                "aggregate": {"recall@5": 1.0, "citation_validity": 1.0},
            }
        ),
        encoding="utf-8",
    )

    summary = write_retrieval_bakeoff(root=tmp_path)

    assert summary["retrieval_bakeoff_complete"] is False
    assert "missing_modes" in summary["failed"]
    assert (tmp_path / "artifacts/retrieval_bakeoff/summary.json").is_file()


def test_write_retrieval_bakeoff_defers_missing_reranker_artifact(
    tmp_path: Path,
) -> None:
    def write_metrics(path: Path, *, retrieval_mode: str, reranker: str | None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "provider_lane": "offline",
                    "retrieval_mode": retrieval_mode,
                    "reranker": reranker,
                    "query_set_counts": {"total": 10},
                    "aggregate": {
                        "recall@5": 1.0,
                        "citation_validity": 1.0,
                        "abstention_pass": 1.0,
                        "section_hit_rate": 1.0,
                        "visual_evidence_hit_rate": 1.0,
                    },
                }
            ),
            encoding="utf-8",
        )

    write_metrics(
        tmp_path / "artifacts/eval/metrics.json",
        retrieval_mode="vector",
        reranker="none",
    )
    write_metrics(
        tmp_path / "artifacts/eval_bm25_offline/metrics.json",
        retrieval_mode="bm25",
        reranker="none",
    )
    write_metrics(
        tmp_path / "artifacts/eval_hybrid_offline/metrics.json",
        retrieval_mode="hybrid",
        reranker="none",
    )
    write_metrics(
        tmp_path / "artifacts/eval_open/metrics.json",
        retrieval_mode="vector",
        reranker="none",
    )

    summary = write_retrieval_bakeoff(root=tmp_path)

    assert "reranker" not in summary["available_modes"]
    assert summary["missing_modes"] == []
    assert "missing_modes" not in summary["failed"]
    assert summary["optional_deferred_modes"]["reranker"]["status"] == "deferred"
    assert summary["retrieval_bakeoff_complete"] is True


def test_write_retrieval_bakeoff_prefers_eval_open_rerank(
    tmp_path: Path,
) -> None:
    def write_metrics(path: Path, *, retrieval_mode: str, reranker: str | None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "provider_lane": "offline",
                    "retrieval_mode": retrieval_mode,
                    "reranker": reranker,
                    "query_set_counts": {"total": 10},
                    "aggregate": {
                        "recall@5": 1.0,
                        "citation_validity": 1.0,
                        "abstention_pass": 1.0,
                        "section_hit_rate": 1.0,
                        "visual_evidence_hit_rate": 1.0,
                    },
                }
            ),
            encoding="utf-8",
        )

    write_metrics(
        tmp_path / "artifacts/eval/metrics.json",
        retrieval_mode="vector",
        reranker="none",
    )
    write_metrics(
        tmp_path / "artifacts/eval_bm25_offline/metrics.json",
        retrieval_mode="bm25",
        reranker="none",
    )
    write_metrics(
        tmp_path / "artifacts/eval_hybrid_offline/metrics.json",
        retrieval_mode="hybrid",
        reranker="none",
    )
    write_metrics(
        tmp_path / "artifacts/eval_open/metrics.json",
        retrieval_mode="vector",
        reranker="none",
    )
    write_metrics(
        tmp_path / "artifacts/eval_open_rerank/metrics.json",
        retrieval_mode="vector",
        reranker="llm",
    )

    summary = write_retrieval_bakeoff(root=tmp_path)

    reranker_run = next(run for run in summary["runs"] if run["name"] == "reranker")
    assert reranker_run["path"].endswith("artifacts/eval_open_rerank/metrics.json")
    assert summary["retrieval_bakeoff_complete"] is True


def test_retrieval_bakeoff_cli_returns_nonzero_until_all_modes_exist(
    tmp_path: Path,
) -> None:
    rc = main(["--root", str(tmp_path)])

    assert rc == 1
    saved = json.loads(
        (tmp_path / "artifacts/retrieval_bakeoff/summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved["retrieval_bakeoff_complete"] is False
