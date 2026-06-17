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
        "judge_coverage_faithfulness": 1.0,
        "judge_coverage_answer_relevancy": 0.92,
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


def test_open_lane_never_claims_quality() -> None:
    # open lane은 이터레이션 신호 전용 — 전 지표 통과여도 게이트를 주장하지 않는다
    gates = decide_gates("open", _passing_aggregate(), evaluation_valid=True)

    assert gates["thresholds_applied"] is False
    assert gates["rag_quality_complete"] is False


def test_open_lane_aggregate_includes_judge_scores() -> None:
    # open lane의 존재 이유: judge 점수를 이터레이션 신호로 본다 — aggregate에 포함돼야 함
    from rfp_rag.evaluate import _lane_aggregate

    prediction = {
        "query_type": "curated_text",
        "pass_fail": {"recall@3": 1.0},
        "judge": {"faithfulness": 0.9, "answer_relevancy": 0.8, "warnings": []},
    }

    aggregate = _lane_aggregate("open", [prediction])

    assert aggregate["faithfulness"] == 0.9
    assert aggregate["answer_relevancy"] == 0.8
    assert aggregate["judge_coverage_faithfulness"] == 1.0


def test_contract_for_lane_selects_matching_contract() -> None:
    from rfp_rag.evaluate import _contract_for

    assert _contract_for("offline")["contract_version"] == "rfp-rag-offline-v3"
    assert _contract_for("real_openai")["contract_version"] == "rfp-rag-real-v4"
    assert _contract_for("open")["contract_version"] == "rfp-rag-open-v3"


def test_open_contract_does_not_claim_gates() -> None:
    from rfp_rag.contracts import open_contract

    semantics = open_contract()["quality_semantics"]["open"]

    assert semantics["claims_semantic_quality"] is False
    assert semantics["forbidden_completion_claim"] == "rag_quality_complete"


def test_real_lane_fails_when_judge_coverage_low() -> None:
    # judge_aborted/judge_error로 빠진 케이스가 평균에서 조용히 제외되어
    # 소수 고득점 케이스만으로 거짓 통과하는 것을 차단한다 (PR #4 Codex 리뷰)
    aggregate = _passing_aggregate() | {
        "judge_coverage_faithfulness": 0.06,
        "judge_coverage_answer_relevancy": 0.06,
    }

    gates = decide_gates("real_openai", aggregate, evaluation_valid=True)

    assert gates["thresholds_met"] is False
    assert gates["rag_quality_complete"] is False


def test_real_lane_fails_when_judge_coverage_missing() -> None:
    aggregate = _passing_aggregate()
    del aggregate["judge_coverage_faithfulness"]

    gates = decide_gates("real_openai", aggregate, evaluation_valid=True)

    assert gates["rag_quality_complete"] is False


def test_judge_coverage_counts_scored_share_of_judged_cases() -> None:
    from rfp_rag.evaluate import _judge_coverage

    predictions = [
        {
            "query_type": "project_budget",
            "judge": {"faithfulness": 0.9, "answer_relevancy": 0.8},
        },
        {
            "query_type": "project_budget",
            "judge": {
                "faithfulness": None,
                "answer_relevancy": None,
                "warnings": ["judge_aborted"],
            },
        },
        {
            "query_type": "abstention",
            "judge": {"faithfulness": None, "answer_relevancy": None},
        },  # 대상 외
    ]
    coverage = _judge_coverage(predictions)

    assert coverage["judge_coverage_faithfulness"] == 0.5
    assert coverage["judge_coverage_answer_relevancy"] == 0.5


def test_real_contract_version_bumped_for_coverage_gate() -> None:
    # 게이트 시맨틱 변경(judge coverage 추가)은 contract 버전 bump가 필수 (CLAUDE.md)
    from rfp_rag.contracts import REAL_CONTRACT_VERSION

    assert REAL_CONTRACT_VERSION == "rfp-rag-real-v4"


def test_thresholds_cover_ragas_metrics() -> None:
    assert RAGAS_THRESHOLDS == {
        "faithfulness": 0.80,
        "answer_relevancy": 0.70,
        "judge_coverage_faithfulness": 0.90,
        "judge_coverage_answer_relevancy": 0.90,
    }
    assert "recall@5" in REAL_QUALITY_THRESHOLDS
