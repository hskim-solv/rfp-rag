from __future__ import annotations

import asyncio
import os
from typing import Any

from .providers import require_openai_key

JUDGED_QUERY_TYPES = {"project_budget", "project_deadline", "issuer_lookup", "project_summary", "curated_text"}


def _build_metrics() -> dict[str, Any]:
    """Real RAGAS metrics. Requires OPENAI_API_KEY."""
    require_openai_key()
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import Faithfulness, ResponseRelevancy

    judge_model = os.environ.get("RFP_JUDGE_MODEL", "gpt-5.4")
    embedding_model = os.environ.get("RFP_EMBEDDING_MODEL", "text-embedding-3-small")
    llm = LangchainLLMWrapper(ChatOpenAI(model=judge_model))
    embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model=embedding_model))
    return {
        "faithfulness": Faithfulness(llm=llm),
        "answer_relevancy": ResponseRelevancy(llm=llm, embeddings=embeddings),
    }


def _sample(prediction: dict[str, Any]):
    from ragas import SingleTurnSample

    return SingleTurnSample(
        user_input=prediction["query"],
        response=prediction["answer"],
        retrieved_contexts=list(prediction.get("source_texts") or []),
    )


async def _score_one(prediction: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    judge: dict[str, Any] = {name: None for name in metrics}
    judge["warnings"] = []
    if prediction.get("query_type") not in JUDGED_QUERY_TYPES:
        judge["warnings"].append("judge_skipped_abstention")
        return judge
    sample = _sample(prediction)
    for name, metric in metrics.items():
        try:
            judge[name] = float(await metric.single_turn_ascore(sample))
        except Exception as exc:  # noqa: BLE001 - judge must not break the eval lane
            judge["warnings"].append(f"judge_error:{name}:{type(exc).__name__}")
    return judge


def judge_predictions(
    predictions: list[dict[str, Any]],
    metrics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Attach a `judge` dict to each prediction. Failures degrade to None scores."""
    metrics = metrics if metrics is not None else _build_metrics()

    async def _run() -> list[dict[str, Any]]:
        return [await _score_one(p, metrics) for p in predictions]

    judges = asyncio.run(_run())
    return [dict(p) | {"judge": j} for p, j in zip(predictions, judges)]
