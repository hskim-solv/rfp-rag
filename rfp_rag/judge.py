from __future__ import annotations

import asyncio
import math
import os
import sys
from typing import Any

from .providers import require_openai_key
from .tracing import tracing_callbacks

# Must stay in sync with the query_type values emitted by evaluate.py's eval-set generators.
# Anything outside this set (today: abstention) is skipped, not judged.
JUDGED_QUERY_TYPES = {
    "project_budget",
    "project_deadline",
    "issuer_lookup",
    "project_summary",
    "curated_text",
}

# mini 기본값: §10-11 A/B에서 gpt-5.4 대비 게이트 판정 일치·이탈 보수적·비용 1/6.
DEFAULT_JUDGE_MODEL = "gpt-5.4-mini"


def _build_metrics() -> dict[str, Any]:
    """Real RAGAS metrics. Requires OPENAI_API_KEY."""
    require_openai_key()
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import Faithfulness, ResponseRelevancy
    from ragas.run_config import RunConfig

    judge_model = os.environ.get("RFP_JUDGE_MODEL", DEFAULT_JUDGE_MODEL)
    embedding_model = os.environ.get("RFP_EMBEDDING_MODEL", "text-embedding-3-small")
    # OpenAI 호환 백엔드(DeepSeek 등)로 judge를 돌리는 오버라이드 (scripts/judge_ab.py).
    # 임베딩(answer_relevancy)은 OpenAI 유지 — OPENAI_API_KEY는 여전히 필요하다.
    llm_kwargs: dict[str, Any] = {}
    judge_base_url = os.environ.get("RFP_JUDGE_BASE_URL")
    if judge_base_url:
        llm_kwargs["base_url"] = judge_base_url
        judge_api_key = os.environ.get("RFP_JUDGE_API_KEY")
        if judge_api_key:
            llm_kwargs["api_key"] = judge_api_key
    llm = LangchainLLMWrapper(
        ChatOpenAI(model=judge_model, callbacks=tracing_callbacks(), **llm_kwargs)
    )
    embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model=embedding_model))
    metrics: dict[str, Any] = {
        "faithfulness": Faithfulness(llm=llm),
        "answer_relevancy": ResponseRelevancy(llm=llm, embeddings=embeddings),
    }
    # ragas 기본 max_retries=10/max_wait=60 — 영구 실패(quota 429)에서 재시도 폭주의
    # 원인 (REPORT §10-10). 일시 장애 회복은 fail-fast(JUDGE_ABORT_AFTER)가 케이스
    # 레벨에서 방어하므로 메트릭 내부 재시도는 짧게 제한한다.
    run_config = RunConfig(max_retries=2, max_wait=15)
    for metric in metrics.values():
        metric.init(run_config)  # llm에 적용 — embeddings는 init이 건드리지 않는다
        metric_embeddings = getattr(metric, "embeddings", None)
        if metric_embeddings is not None:
            metric_embeddings.set_run_config(run_config)
    return metrics


def _sample(prediction: dict[str, Any]):
    from ragas import SingleTurnSample

    return SingleTurnSample(
        user_input=prediction["query"],
        response=prediction["answer"],
        retrieved_contexts=list(prediction.get("source_texts") or []),
    )


async def _score_one(
    prediction: dict[str, Any], metrics: dict[str, Any]
) -> dict[str, Any]:
    judge: dict[str, Any] = {name: None for name in metrics}
    judge["warnings"] = []
    if prediction.get("query_type") not in JUDGED_QUERY_TYPES:
        judge["warnings"].append("judge_skipped_abstention")
        return judge
    sample = _sample(prediction)
    for name, metric in metrics.items():
        try:
            score = float(await metric.single_turn_ascore(sample))
            if math.isnan(score):
                judge["warnings"].append(f"judge_nan:{name}")
            else:
                judge[name] = score
        except Exception as exc:  # noqa: BLE001 - judge must not break the eval lane
            judge["warnings"].append(f"judge_error:{name}:{type(exc).__name__}")
    return judge


# 연속 전건(judge_error) 실패 케이스가 이 수에 도달하면 잔여 케이스를 호출 없이 스킵.
# quota 소진 같은 영구 실패에서 재시도 콜 폭주를 차단한다 (REPORT §10-10: 644콜 전부 429).
JUDGE_ABORT_AFTER = 3


def _is_total_failure(judge: dict[str, Any], metrics: dict[str, Any]) -> bool:
    errors = [w for w in judge["warnings"] if w.startswith("judge_error:")]
    return bool(metrics) and len(errors) >= len(metrics)


def judge_predictions(
    predictions: list[dict[str, Any]],
    metrics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Attach a `judge` dict to each prediction. Failures degrade to None scores."""
    metrics = metrics if metrics is not None else _build_metrics()

    async def _run() -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        consecutive = 0
        aborted = False
        for p in predictions:
            if aborted:
                skipped: dict[str, Any] = {name: None for name in metrics}
                skipped["warnings"] = ["judge_aborted"]
                out.append(skipped)
                continue
            judge = await _score_one(p, metrics)
            out.append(judge)
            if "judge_skipped_abstention" in judge["warnings"]:
                continue  # 채점 미시도 — 연속 실패 카운터에 무영향
            if _is_total_failure(judge, metrics):
                consecutive += 1
                if consecutive >= JUDGE_ABORT_AFTER:
                    aborted = True
                    remaining = len(predictions) - len(out)
                    print(
                        f"warning: judge aborted after {consecutive} consecutive total "
                        f"failures — skipping {remaining} remaining case(s)",
                        file=sys.stderr,
                    )
            else:
                consecutive = 0
        return out

    judges = asyncio.run(_run())
    return [dict(p) | {"judge": j} for p, j in zip(predictions, judges)]
