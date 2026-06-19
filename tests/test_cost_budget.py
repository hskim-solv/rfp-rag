from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.cost_budget import evaluate_cost_budget, main


def _write_eval_dir(root: Path, rel: str, provider_lane: str, count: int = 2) -> None:
    eval_dir = root / rel
    eval_dir.mkdir(parents=True)
    (eval_dir / "metrics.json").write_text(
        json.dumps({"provider_lane": provider_lane}), encoding="utf-8"
    )
    rows = [
        {
            "query": f"질문 {idx}",
            "source_texts": ["근거 텍스트"],
            "answer": "답변 텍스트",
            "warnings": [],
        }
        for idx in range(count)
    ]
    (eval_dir / "predictions.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_evaluate_cost_budget_writes_stage2_contract_artifact(tmp_path: Path) -> None:
    _write_eval_dir(tmp_path, "artifacts/eval_real", "real_openai")
    _write_eval_dir(tmp_path, "artifacts/eval_open", "open")

    summary = evaluate_cost_budget(root=tmp_path, max_estimated_cost_usd=5.0)

    assert summary["cost_budget_complete"] is True
    assert summary["real_open_run_cost_estimate_usd"] > 0
    assert summary["metrics"] == {
        "budget_violation_count": 0,
        "cost_record_coverage": 1.0,
        "token_record_coverage": 1.0,
    }
    assert summary["failed"] == []
    assert (tmp_path / "artifacts/cost_budget/summary.json").is_file()


def test_evaluate_cost_budget_includes_optional_paid_eval_artifacts(
    tmp_path: Path,
) -> None:
    _write_eval_dir(tmp_path, "artifacts/eval_real", "real_openai", count=2)
    _write_eval_dir(tmp_path, "artifacts/eval_open", "open", count=2)
    _write_eval_dir(tmp_path, "artifacts/eval_open_rerank", "open", count=3)
    _write_eval_dir(tmp_path, "artifacts/eval_stage2_real", "real_openai", count=4)

    summary = evaluate_cost_budget(root=tmp_path, max_estimated_cost_usd=5.0)

    assert summary["cost_budget_complete"] is True
    assert summary["reranker_run_cost_estimate_usd"] > 0
    assert summary["stage2_real_run_cost_estimate_usd"] > 0
    assert summary["prediction_counts"] == {
        "eval_open": 2,
        "eval_open_rerank": 3,
        "eval_real": 2,
        "eval_real_rerank": 0,
        "eval_stage2_real": 4,
    }
    assert "artifacts/eval_open_rerank" in summary["measured_eval_dirs"]
    assert "artifacts/eval_stage2_real" in summary["measured_eval_dirs"]


def test_evaluate_cost_budget_fails_missing_real_predictions(tmp_path: Path) -> None:
    summary = evaluate_cost_budget(root=tmp_path)

    assert summary["cost_budget_complete"] is False
    assert summary["metrics"]["token_record_coverage"] == 0.0
    assert "token_record_coverage" in summary["failed"]


def test_cost_budget_cli_writes_summary(tmp_path: Path) -> None:
    _write_eval_dir(tmp_path, "artifacts/eval_real", "real_openai")
    _write_eval_dir(tmp_path, "artifacts/eval_open", "open")

    rc = main(["--root", str(tmp_path)])

    assert rc == 0
    saved = json.loads(
        (tmp_path / "artifacts/cost_budget/summary.json").read_text(encoding="utf-8")
    )
    assert saved["cost_budget_complete"] is True
