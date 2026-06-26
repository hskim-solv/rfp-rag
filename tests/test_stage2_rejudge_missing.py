from __future__ import annotations

import json
from pathlib import Path

from rfp_rag import stage2_rejudge_missing


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_rejudge_missing_stage2_judges_only_missing_rows(
    tmp_path: Path, monkeypatch
) -> None:
    out_dir = tmp_path / "artifacts/eval_stage2_real"
    _write_jsonl(
        out_dir / "predictions.jsonl",
        [
            {
                "query_id": "metadata_budget_000",
                "query_type": "project_budget",
                "judge": {"faithfulness": 1.0, "answer_relevancy": 1.0},
            },
            {
                "query_id": "paraphrase_000",
                "query_type": "paraphrase",
                "judge": {"faithfulness": None, "answer_relevancy": 0.8},
            },
            {
                "query_id": "abstention_000",
                "query_type": "abstention",
                "judge": {"warnings": ["judge_skipped_abstention"]},
            },
        ],
    )
    judged_targets: list[dict] = []

    def fake_judge_predictions(rows: list[dict]) -> list[dict]:
        judged_targets.extend(rows)
        return [
            dict(row) | {"judge": {"faithfulness": 0.99, "answer_relevancy": 0.98}}
            for row in rows
        ]

    monkeypatch.setattr(
        stage2_rejudge_missing, "judge_predictions", fake_judge_predictions
    )
    monkeypatch.setattr(stage2_rejudge_missing, "flush_tracing", lambda: None)
    monkeypatch.setattr(
        stage2_rejudge_missing,
        "reaggregate_metrics",
        lambda out, provider: {"provider_lane": provider},
    )
    monkeypatch.setattr(
        stage2_rejudge_missing,
        "finalize_stage2_real",
        lambda **kwargs: {"holdout_quality_complete": True},
    )

    summary = stage2_rejudge_missing.rejudge_missing_stage2(
        root=tmp_path, out_dir=out_dir
    )

    assert summary["stage2_rejudge_missing_complete"] is True
    assert summary["missing_judged_count"] == 1
    assert [row["query_id"] for row in judged_targets] == ["paraphrase_000"]
    rows = [
        json.loads(line)
        for line in (out_dir / "predictions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert rows[0]["judge"]["faithfulness"] == 1.0
    assert rows[1]["judge"] == {"faithfulness": 0.99, "answer_relevancy": 0.98}
    assert rows[2]["judge"]["warnings"] == ["judge_skipped_abstention"]


def test_rejudge_missing_stage2_skips_api_when_no_missing_rows(
    tmp_path: Path, monkeypatch
) -> None:
    out_dir = tmp_path / "artifacts/eval_stage2_real"
    _write_jsonl(
        out_dir / "predictions.jsonl",
        [
            {
                "query_id": "metadata_budget_000",
                "query_type": "project_budget",
                "judge": {"faithfulness": 1.0, "answer_relevancy": 1.0},
            }
        ],
    )

    def unexpected_judge_predictions(rows: list[dict]) -> list[dict]:
        raise AssertionError("judge should not run when all rows are scored")

    monkeypatch.setattr(
        stage2_rejudge_missing, "judge_predictions", unexpected_judge_predictions
    )
    monkeypatch.setattr(
        stage2_rejudge_missing,
        "reaggregate_metrics",
        lambda out, provider: {"provider_lane": provider},
    )
    monkeypatch.setattr(
        stage2_rejudge_missing,
        "finalize_stage2_real",
        lambda **kwargs: {"holdout_quality_complete": True},
    )

    summary = stage2_rejudge_missing.rejudge_missing_stage2(
        root=tmp_path, out_dir=out_dir
    )

    assert summary["stage2_rejudge_missing_complete"] is True
    assert summary["missing_judged_count"] == 0
