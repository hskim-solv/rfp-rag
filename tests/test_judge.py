from __future__ import annotations

from rfp_rag.judge import judge_predictions


class _StubMetric:
    def __init__(self, name: str, score: float | Exception) -> None:
        self.name = name
        self._score = score

    async def single_turn_ascore(self, sample) -> float:
        if isinstance(self._score, Exception):
            raise self._score
        return self._score


def _prediction(query_type: str = "curated_text") -> dict:
    return {
        "query_id": "q1",
        "query": "사업 요약해줘",
        "query_type": query_type,
        "answer": "본 사업은 학사정보시스템 고도화이다.",
        "sources": [{"chunk_id": "doc:000:chunk:0"}],
        "source_texts": ["학사정보시스템 고도화 사업 본문"],
    }


def test_judge_scores_each_prediction() -> None:
    metrics = {"faithfulness": _StubMetric("faithfulness", 0.9), "answer_relevancy": _StubMetric("answer_relevancy", 0.8)}

    judged = judge_predictions([_prediction()], metrics=metrics)

    assert judged[0]["judge"]["faithfulness"] == 0.9
    assert judged[0]["judge"]["answer_relevancy"] == 0.8
    assert judged[0]["judge"]["warnings"] == []


def test_judge_skips_abstention_questions() -> None:
    metrics = {"faithfulness": _StubMetric("faithfulness", 0.9)}

    judged = judge_predictions([_prediction(query_type="abstention")], metrics=metrics)

    assert judged[0]["judge"]["faithfulness"] is None
    assert "judge_skipped_abstention" in judged[0]["judge"]["warnings"]


def test_judge_failure_is_isolated_per_metric() -> None:
    metrics = {
        "faithfulness": _StubMetric("faithfulness", RuntimeError("api down")),
        "answer_relevancy": _StubMetric("answer_relevancy", 0.7),
    }

    judged = judge_predictions([_prediction()], metrics=metrics)

    assert judged[0]["judge"]["faithfulness"] is None
    assert judged[0]["judge"]["answer_relevancy"] == 0.7
    assert any(w.startswith("judge_error:faithfulness") for w in judged[0]["judge"]["warnings"])


def test_judge_nan_score_degrades_to_none_with_warning() -> None:
    metrics = {"answer_relevancy": _StubMetric("answer_relevancy", float("nan"))}

    judged = judge_predictions([_prediction()], metrics=metrics)

    assert judged[0]["judge"]["answer_relevancy"] is None
    assert "judge_nan:answer_relevancy" in judged[0]["judge"]["warnings"]


def test_judge_empty_predictions_returns_empty_list() -> None:
    assert judge_predictions([], metrics={}) == []
