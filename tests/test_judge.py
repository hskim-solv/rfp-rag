from __future__ import annotations

import pytest

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
    metrics = {
        "faithfulness": _StubMetric("faithfulness", 0.9),
        "answer_relevancy": _StubMetric("answer_relevancy", 0.8),
    }

    judged = judge_predictions([_prediction()], metrics=metrics)

    assert judged[0]["judge"]["faithfulness"] == 0.9
    assert judged[0]["judge"]["answer_relevancy"] == 0.8
    assert judged[0]["judge"]["warnings"] == []


def test_judge_progress_callback_receives_judged_rows() -> None:
    metrics = {"faithfulness": _StubMetric("faithfulness", 0.9)}
    seen: list[tuple[int, dict]] = []

    judged = judge_predictions(
        [_prediction(), _prediction(query_type="abstention")],
        metrics=metrics,
        on_judged=lambda idx, row: seen.append((idx, row)),
    )

    assert len(seen) == 2
    assert seen[0][0] == 0
    assert seen[0][1]["judge"]["faithfulness"] == 0.9
    assert seen[1][0] == 1
    assert "judge_skipped_abstention" in seen[1][1]["judge"]["warnings"]
    assert judged == [row for _, row in seen]


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
    assert any(
        w.startswith("judge_error:faithfulness") for w in judged[0]["judge"]["warnings"]
    )


def test_judge_nan_score_degrades_to_none_with_warning() -> None:
    metrics = {"answer_relevancy": _StubMetric("answer_relevancy", float("nan"))}

    judged = judge_predictions([_prediction()], metrics=metrics)

    assert judged[0]["judge"]["answer_relevancy"] is None
    assert "judge_nan:answer_relevancy" in judged[0]["judge"]["warnings"]


def test_judge_empty_predictions_returns_empty_list() -> None:
    assert judge_predictions([], metrics={}) == []


@pytest.mark.filterwarnings(
    "ignore::DeprecationWarning"
)  # ragas 구 import 경로 — ADR-0002 재검토 조건으로 기록됨
def test_build_metrics_defaults_to_mini_judge(monkeypatch) -> None:
    # §10-11 A/B: mini는 게이트 판정 일치·이탈 보수적·비용 1/6 — 기본값으로 채택
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("RFP_JUDGE_MODEL", raising=False)
    monkeypatch.delenv("RFP_JUDGE_BASE_URL", raising=False)
    from rfp_rag.judge import _build_metrics

    metrics = _build_metrics()

    for name, metric in metrics.items():
        assert metric.llm.langchain_llm.model_name == "gpt-5.4-mini", name


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_build_metrics_supports_base_url_override(monkeypatch) -> None:
    # DeepSeek 같은 OpenAI 호환 백엔드로 judge를 돌리는 경로 (scripts/judge_ab.py A/B용).
    # 임베딩(answer_relevancy)은 OpenAI 유지 — OPENAI_API_KEY는 여전히 필요하다.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("RFP_JUDGE_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("RFP_JUDGE_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("RFP_JUDGE_API_KEY", "sk-deepseek-test")
    from rfp_rag.judge import _build_metrics

    metrics = _build_metrics()

    for name, metric in metrics.items():
        llm = metric.llm.langchain_llm
        assert llm.model_name == "deepseek-v4-flash", name
        assert llm.openai_api_base == "https://api.deepseek.com", name
        assert llm.openai_api_key.get_secret_value() == "sk-deepseek-test", name
        # 임베딩은 base_url 오버라이드의 영향을 받지 않는다
        embeddings = getattr(metric, "embeddings", None)
        if embeddings is not None:
            assert embeddings.embeddings.openai_api_base is None, name


@pytest.mark.filterwarnings(
    "ignore::DeprecationWarning"
)  # ragas 구 import 경로 — ADR-0002 재검토 조건으로 기록됨
def test_build_metrics_caps_ragas_retries(monkeypatch) -> None:
    # ragas RunConfig 기본 max_retries=10 — 영구 실패(quota)에서 재시도 폭주의 원인 (REPORT §10-10).
    # 가짜 키로 인스턴스만 생성 — 네트워크 호출 없음.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from rfp_rag.judge import _build_metrics

    metrics = _build_metrics()
    for name, metric in metrics.items():
        assert metric.llm.run_config.max_retries <= 2, name
        embeddings = getattr(metric, "embeddings", None)
        if embeddings is not None:
            assert embeddings.run_config.max_retries <= 2, name


class _CountingFailMetric:
    """항상 실패하며 호출 횟수를 기록 — quota 소진(영구 실패) 시뮬레이션."""

    def __init__(self, calls: dict) -> None:
        self._calls = calls

    async def single_turn_ascore(self, sample) -> float:
        self._calls["n"] += 1
        raise RuntimeError("insufficient_quota")


def test_judge_aborts_after_consecutive_total_failures() -> None:
    # 전 케이스가 전 메트릭 에러면 연속 3건 후 잔여 케이스는 호출 없이 스킵한다
    calls = {"n": 0}
    metrics = {
        "faithfulness": _CountingFailMetric(calls),
        "answer_relevancy": _CountingFailMetric(calls),
    }
    judged = judge_predictions([_prediction() for _ in range(10)], metrics=metrics)

    assert calls["n"] == 6  # 3건 × 2메트릭에서 멈춤 — 644콜 폭주 재발 방지
    assert len(judged) == 10  # 파이프라인 계약 보존: 입력 길이 유지
    for j in judged[3:]:
        assert j["judge"]["faithfulness"] is None
        assert "judge_aborted" in j["judge"]["warnings"]


def test_judge_abort_counter_resets_on_partial_success() -> None:
    # 한 메트릭이라도 성공하면 '전건 실패'가 아니므로 카운터가 리셋된다
    calls = {"n": 0}

    class _FlakyMetric:
        """3번째 케이스만 성공 — 연속 전건 실패가 3에 도달하지 않게 한다."""

        def __init__(self) -> None:
            self._i = 0

        async def single_turn_ascore(self, sample) -> float:
            self._i += 1
            if self._i == 3:
                return 0.9
            raise RuntimeError("api down")

    metrics = {
        "faithfulness": _FlakyMetric(),
        "answer_relevancy": _CountingFailMetric(calls),
    }
    judged = judge_predictions([_prediction() for _ in range(5)], metrics=metrics)

    assert all("judge_aborted" not in j["judge"]["warnings"] for j in judged)
    assert judged[2]["judge"]["faithfulness"] == 0.9


def test_judge_abort_ignores_abstention_cases() -> None:
    # abstention(채점 미시도)은 연속 실패 카운터를 끊지 않는다
    calls = {"n": 0}
    metrics = {"faithfulness": _CountingFailMetric(calls)}
    preds = [
        _prediction(),
        _prediction(),
        _prediction(query_type="abstention"),
        _prediction(),
        _prediction(),
    ]
    judged = judge_predictions(preds, metrics=metrics)

    assert calls["n"] == 3  # 시도 케이스 3건(인덱스 0,1,3)에서 중단
    assert "judge_skipped_abstention" in judged[2]["judge"]["warnings"]
    assert "judge_aborted" in judged[4]["judge"]["warnings"]
