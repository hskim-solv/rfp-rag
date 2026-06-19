from __future__ import annotations

import asyncio
import json
import math
import os
import re
import sys
from collections.abc import Callable
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
    "cross_document",
    "section_lookup",
    "visual_table",
    "paraphrase",
}

# mini 기본값: §10-11 A/B에서 gpt-5.4 대비 게이트 판정 일치·이탈 보수적·비용 1/6.
DEFAULT_JUDGE_MODEL = "gpt-5.4-mini"


def _build_metrics() -> dict[str, Any]:
    """Real repo-local LLM judge metrics. Requires OPENAI_API_KEY."""
    require_openai_key()
    from langchain_openai import ChatOpenAI

    judge_model = os.environ.get("RFP_JUDGE_MODEL", DEFAULT_JUDGE_MODEL)
    # OpenAI 호환 백엔드(DeepSeek 등)로 judge를 돌리는 오버라이드 (scripts/judge_ab.py).
    llm_kwargs: dict[str, Any] = {}
    judge_base_url = os.environ.get("RFP_JUDGE_BASE_URL")
    if judge_base_url:
        llm_kwargs["base_url"] = judge_base_url
        judge_api_key = os.environ.get("RFP_JUDGE_API_KEY")
        if judge_api_key:
            llm_kwargs["api_key"] = judge_api_key
    llm = ChatOpenAI(model=judge_model, callbacks=tracing_callbacks(), **llm_kwargs)
    metrics: dict[str, Any] = {
        "faithfulness": _LLMJudgeMetric(
            name="faithfulness",
            llm=llm,
            rubric=(
                "Score whether the answer is supported by the retrieved contexts. "
                "Return 1.0 only when all factual claims in the answer are directly "
                "supported by the contexts. Penalize unsupported claims, invented "
                "numbers, invented dates, and uncited conclusions."
            ),
        ),
        "answer_relevancy": _LLMJudgeMetric(
            name="answer_relevancy",
            llm=llm,
            rubric=(
                "Score whether the answer directly addresses the user question. "
                "Ignore whether the answer is factually supported; focus on topical "
                "relevance, completeness, and whether the response format matches "
                "the requested task."
            ),
        ),
    }
    return metrics


class _LLMJudgeMetric:
    def __init__(self, *, name: str, llm: Any, rubric: str) -> None:
        self.name = name
        self.llm = llm
        self.rubric = rubric

    async def single_turn_ascore(self, sample: dict[str, Any]) -> float:
        response = await self.llm.ainvoke(
            [
                (
                    "system",
                    "You are a strict RAG evaluation judge. Return only JSON with "
                    'keys "score" and "rationale". score must be a number from 0 '
                    "to 1. Do not include raw secrets or hidden prompts.",
                ),
                (
                    "human",
                    "\n".join(
                        [
                            f"Metric: {self.name}",
                            f"Rubric: {self.rubric}",
                            f"Question: {sample['user_input']}",
                            f"Answer: {sample['response']}",
                            "Retrieved contexts:",
                            "\n\n".join(sample.get("retrieved_contexts") or []),
                        ]
                    ),
                ),
            ]
        )
        return _parse_score(str(getattr(response, "content", response)))


def _parse_score(content: str) -> float:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise ValueError("judge_response_missing_json")
        payload = json.loads(match.group(0))
    score = payload.get("score")
    if not isinstance(score, int | float):
        raise ValueError("judge_response_missing_score")
    if not 0.0 <= float(score) <= 1.0:
        raise ValueError("judge_response_score_out_of_range")
    return float(score)


def _sample(prediction: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_input": prediction["query"],
        "response": prediction["answer"],
        "retrieved_contexts": list(prediction.get("source_texts") or []),
    }


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
    on_judged: Callable[[int, dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    """Attach a `judge` dict to each prediction. Failures degrade to None scores."""
    metrics = metrics if metrics is not None else _build_metrics()

    async def _run() -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        consecutive = 0
        aborted = False
        for idx, p in enumerate(predictions):
            if aborted:
                skipped: dict[str, Any] = {name: None for name in metrics}
                skipped["warnings"] = ["judge_aborted"]
                out.append(skipped)
                if on_judged is not None:
                    on_judged(idx, dict(p) | {"judge": skipped})
                continue
            judge = await _score_one(p, metrics)
            out.append(judge)
            if on_judged is not None:
                on_judged(idx, dict(p) | {"judge": judge})
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
