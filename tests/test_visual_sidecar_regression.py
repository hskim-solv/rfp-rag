from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.visual_sidecar_regression import (
    compare_sidecar_predictions,
    write_sidecar_regression,
)


def _prediction(
    query_id: str,
    query_type: str,
    pass_fail: dict[str, float | None],
) -> dict:
    return {
        "query_id": query_id,
        "query_type": query_type,
        "pass_fail": pass_fail,
    }


def test_compare_sidecar_predictions_passes_when_on_does_not_regress() -> None:
    summary = compare_sidecar_predictions(
        sidecar_on=[
            _prediction("visual_1", "visual_table", {"citation_validity": 1.0}),
            _prediction("abstain_1", "abstention", {"abstention_pass": 1.0}),
        ],
        sidecar_off=[
            _prediction("visual_1", "visual_table", {"citation_validity": 1.0}),
            _prediction("abstain_1", "abstention", {"abstention_pass": 1.0}),
        ],
    )

    assert summary["sidecar_citation_no_regression"] is True
    assert summary["sidecar_abstention_no_regression"] is True
    assert summary["failed"] == []


def test_compare_sidecar_predictions_fails_when_on_regresses() -> None:
    summary = compare_sidecar_predictions(
        sidecar_on=[
            _prediction("visual_1", "visual_table", {"citation_validity": 0.0}),
            _prediction("abstain_1", "abstention", {"abstention_pass": 1.0}),
        ],
        sidecar_off=[
            _prediction("visual_1", "visual_table", {"citation_validity": 1.0}),
            _prediction("abstain_1", "abstention", {"abstention_pass": 1.0}),
        ],
    )

    assert summary["sidecar_citation_no_regression"] is False
    assert summary["sidecar_abstention_no_regression"] is True
    assert summary["failed"] == ["sidecar_citation_no_regression"]


def test_write_sidecar_regression_writes_summary(tmp_path: Path) -> None:
    out = tmp_path / "sidecar_regression.json"

    summary = write_sidecar_regression(
        sidecar_on=[
            _prediction("visual_1", "visual_table", {"citation_validity": 1.0}),
            _prediction("abstain_1", "abstention", {"abstention_pass": 1.0}),
        ],
        sidecar_off=[
            _prediction("visual_1", "visual_table", {"citation_validity": 1.0}),
            _prediction("abstain_1", "abstention", {"abstention_pass": 1.0}),
        ],
        out=out,
    )

    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved == summary
    assert saved["visual_sidecar_regression_complete"] is True
