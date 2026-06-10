from __future__ import annotations

from rfp_rag.evaluate import REAL_QUALITY_THRESHOLDS, RAGAS_THRESHOLDS, decide_gates


def _passing_aggregate() -> dict:
    return {
        "recall@3": 0.9,
        "recall@5": 0.95,
        "mrr": 0.9,
        "citation_presence": 1.0,
        "citation_validity": 0.95,
        "metadata_exact_match": 0.95,
        "abstention_pass": 1.0,
        "faithfulness": 0.85,
        "answer_relevancy": 0.75,
    }


def test_real_lane_passes_when_all_thresholds_met() -> None:
    gates = decide_gates("real_openai", _passing_aggregate(), evaluation_valid=True)

    assert gates["thresholds_applied"] is True
    assert gates["thresholds_met"] is True
    assert gates["rag_quality_complete"] is True


def test_real_lane_fails_below_any_threshold() -> None:
    aggregate = _passing_aggregate() | {"recall@5": 0.8}

    gates = decide_gates("real_openai", aggregate, evaluation_valid=True)

    assert gates["thresholds_met"] is False
    assert gates["rag_quality_complete"] is False


def test_real_lane_fails_when_evaluation_invalid() -> None:
    gates = decide_gates("real_openai", _passing_aggregate(), evaluation_valid=False)

    # thresholds_met alone is not sufficient: evaluation_valid is also required.
    assert gates["thresholds_met"] is True
    assert gates["rag_quality_complete"] is False


def test_offline_lane_never_claims_quality() -> None:
    gates = decide_gates("offline", _passing_aggregate(), evaluation_valid=True)

    assert gates["thresholds_applied"] is False
    assert gates["thresholds_met"] is False
    assert gates["rag_quality_complete"] is False
    assert gates["offline_scaffold_complete"] is True


def test_thresholds_cover_ragas_metrics() -> None:
    assert RAGAS_THRESHOLDS == {"faithfulness": 0.80, "answer_relevancy": 0.70}
    assert "recall@5" in REAL_QUALITY_THRESHOLDS
