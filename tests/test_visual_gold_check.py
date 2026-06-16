from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.visual_facts import check_visual_gold_summary


def _summary(**overrides: object) -> dict[str, object]:
    summary: dict[str, object] = {
        "decision": "reviewer_visual_fact_gold_set",
        "record_count": 10,
        "reviewed_needs_extraction_count": 5,
        "accepted_record_count": 4,
        "accepted_record_ratio": 0.8,
        "fact_count": 4,
        "accepted_fact_count": 4,
        "rejected_fact_count": 0,
        "needs_review_fact_count": 0,
        "unsupported_claim_count": 0,
        "unknown_record_count": 0,
    }
    summary.update(overrides)
    return summary


def test_visual_gold_gate_passes_when_thresholds_are_met() -> None:
    result = check_visual_gold_summary(_summary())

    assert result["ok"] is True
    assert result["decision"] == "visual_gold_gate"
    assert result["failures"] == []
    assert result["thresholds"]["min_accepted_record_ratio"] == 0.8


def test_visual_gold_gate_fails_when_coverage_is_too_low() -> None:
    result = check_visual_gold_summary(
        _summary(accepted_record_count=1, accepted_record_ratio=0.2)
    )

    assert result["ok"] is False
    assert result["failures"] == [
        {
            "metric": "accepted_record_ratio",
            "actual": 0.2,
            "threshold": 0.8,
            "comparator": ">=",
        }
    ]


def test_visual_gold_gate_fails_when_review_is_unresolved() -> None:
    result = check_visual_gold_summary(
        _summary(needs_review_fact_count=1, unknown_record_count=1)
    )

    assert result["ok"] is False
    assert {
        "metric": "needs_review_fact_count",
        "actual": 1,
        "threshold": 0,
        "comparator": "<=",
    } in result["failures"]
    assert {
        "metric": "unknown_record_count",
        "actual": 1,
        "threshold": 0,
        "comparator": "<=",
    } in result["failures"]


def test_run_visual_gold_check_cli_exits_nonzero_for_failed_summary(
    tmp_path: Path, capsys
) -> None:
    from rfp_rag.run_visual_gold_check import main

    summary_path = tmp_path / "summary.json"
    summary_path.write_text(
        json.dumps(_summary(accepted_record_count=1, accepted_record_ratio=0.2)),
        encoding="utf-8",
    )

    assert main(["--summary", str(summary_path)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["failures"][0]["metric"] == "accepted_record_ratio"
