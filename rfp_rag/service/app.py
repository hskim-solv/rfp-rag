from __future__ import annotations

import json
import time
from collections.abc import AsyncIterable
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from rfp_rag.gate_status import collect_gate_status
from rfp_rag.guardrails import check_question_guardrails
from rfp_rag.ops_metrics import summarize_audit_log, summarize_eval_artifacts
from rfp_rag.path_safety import ArtifactPathError, safe_artifact_path
from rfp_rag.rag_chain import DEFAULT_MIN_SCORE, answer_query
from rfp_rag.rerank import RERANKER_NONE
from rfp_rag.vector_index import RETRIEVAL_VECTOR


class AnswerRequest(BaseModel):
    question: str = Field(min_length=1)
    index_dir: Path = Path("artifacts/index")
    provider: Literal["offline"] | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = DEFAULT_MIN_SCORE
    retrieval_mode: Literal["vector"] = RETRIEVAL_VECTOR
    reranker: Literal["none"] = RERANKER_NONE
    rerank_candidate_k: int | None = Field(default=None, ge=1, le=100)
    visual_candidates: Path | None = None
    visual_gate: Path | None = None

    @field_validator("index_dir")
    @classmethod
    def _validate_index_dir(cls, value: Path) -> Path:
        return safe_artifact_path(value, allowed_relatives=("artifacts/index",))

    @model_validator(mode="after")
    def _validate_visual_paths(self) -> "AnswerRequest":
        if self.visual_candidates is not None:
            self.visual_candidates = safe_artifact_path(
                self.visual_candidates,
                allowed_prefixes=("artifacts",),
                expected_name="records.jsonl",
            )
        if self.visual_gate is not None:
            self.visual_gate = safe_artifact_path(
                self.visual_gate,
                allowed_prefixes=("artifacts",),
                expected_name="summary.json",
            )
        return self


class Source(BaseModel):
    doc_id: str | None = None
    chunk_id: str | None = None
    score: float | None = None
    csv_row_id: str | None = None
    project_name: str | None = None
    issuer: str | None = None
    filename: str | None = None
    section_title: str | None = None
    section_type: str | None = None
    section_path: list[str] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    visual_evidence: list[dict[str, Any]] = Field(default_factory=list)


class AnswerMetadata(BaseModel):
    provider: str | None = None
    index_dir: str
    latency_ms: float
    top_k: int
    min_score: float
    retrieval_mode: str
    reranker: str
    rerank_candidate_k: int | None = None


class AnswerResponse(BaseModel):
    answer: str
    confidence: Literal["low", "medium", "high"] | str = "low"
    warnings: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    retrieved_doc_ids: list[str] = Field(default_factory=list)
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    scores: list[float] = Field(default_factory=list)
    metadata: AnswerMetadata


class HealthResponse(BaseModel):
    ok: bool
    service: str


class OpsSummaryResponse(BaseModel):
    eval: dict[str, Any]
    tools: dict[str, Any]


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    retryable: bool = False


def _error_envelope(
    code: str, message: str, *, retryable: bool = False
) -> dict[str, Any]:
    return ErrorEnvelope(code=code, message=message, retryable=retryable).model_dump()


def _to_answer_response(
    request: AnswerRequest, raw: dict[str, Any], latency_ms: float
) -> AnswerResponse:
    return AnswerResponse(
        answer=str(raw.get("answer") or ""),
        confidence=raw.get("confidence") or "low",
        warnings=list(raw.get("warnings") or []),
        sources=[Source.model_validate(source) for source in raw.get("sources") or []],
        retrieved_doc_ids=list(raw.get("retrieved_doc_ids") or []),
        retrieved_chunk_ids=list(raw.get("retrieved_chunk_ids") or []),
        scores=[float(score) for score in raw.get("scores") or []],
        metadata=AnswerMetadata(
            provider=request.provider,
            index_dir=str(request.index_dir),
            latency_ms=latency_ms,
            top_k=request.top_k,
            min_score=request.min_score,
            retrieval_mode=request.retrieval_mode,
            reranker=raw.get("reranker") or request.reranker,
            rerank_candidate_k=raw.get("rerank_candidate_k"),
        ),
    )


async def _answer(request: AnswerRequest) -> AnswerResponse:
    guardrail = check_question_guardrails(request.question)
    if not guardrail.allowed:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "guardrail_blocked",
                "categories": guardrail.categories,
                "reasons": guardrail.reasons,
            },
        )
    started = time.perf_counter()
    raw = await run_in_threadpool(
        answer_query,
        request.index_dir,
        request.question,
        top_k=request.top_k,
        min_score=request.min_score,
        provider=request.provider,
        retrieval_mode=request.retrieval_mode,
        reranker=request.reranker,
        rerank_candidate_k=request.rerank_candidate_k,
        visual_candidate_path=request.visual_candidates,
        visual_gate_path=request.visual_gate,
    )
    latency_ms = (time.perf_counter() - started) * 1000
    return _to_answer_response(request, raw, latency_ms)


def _sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, sort_keys=True)}\n\n"


async def _answer_events(request: AnswerRequest) -> AsyncIterable[str]:
    yield _sse_event("status", {"status": "started"})
    try:
        response = await _answer(request)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        yield _sse_event(
            "error",
            _error_envelope(
                str(detail.get("code") or "http_error"),
                str(detail.get("message") or detail.get("reasons") or exc.detail),
            )
            | {"status_code": exc.status_code},
        )
        return
    except Exception as exc:  # noqa: BLE001 - SSE must fail closed with a typed event
        yield _sse_event(
            "error",
            _error_envelope("internal_error", type(exc).__name__, retryable=True),
        )
        return
    yield _sse_event("final", response.model_dump(mode="json"))


def create_app() -> FastAPI:
    app = FastAPI(
        title="RFP RAG Service",
        version="0.1.0",
        description=(
            "Typed local-reviewer API surface for source-first Korean public RFP RAG. "
            "Hosted auth/rate-limit profiles are intentionally separate."
        ),
    )

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse(ok=True, service="rfp-rag")

    @app.post("/v1/answer", response_model=AnswerResponse)
    async def answer(request: AnswerRequest) -> AnswerResponse:
        return await _answer(request)

    @app.post("/v1/answer/stream")
    async def answer_stream(request: AnswerRequest) -> StreamingResponse:
        return StreamingResponse(
            _answer_events(request), media_type="text/event-stream"
        )

    @app.get("/v1/gates")
    async def gates(root: Path = Query(default=Path("."))) -> dict[str, Any]:
        try:
            safe_root = safe_artifact_path(
                root,
                allowed_relatives=(".",),
            )
        except ArtifactPathError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        return collect_gate_status(safe_root)

    @app.get("/v1/ops/summary", response_model=OpsSummaryResponse)
    async def ops_summary(
        eval_dir: Path = Query(default=Path("artifacts/eval")),
        audit_path: Path = Query(
            default=Path("artifacts/eval_agent/agent_artifacts/audit.jsonl")
        ),
        input_cost_per_1k: float = Query(default=0.0, ge=0.0),
        output_cost_per_1k: float = Query(default=0.0, ge=0.0),
    ) -> OpsSummaryResponse:
        try:
            safe_eval_dir = safe_artifact_path(
                eval_dir, allowed_prefixes=("artifacts",)
            )
            safe_audit_path = safe_artifact_path(
                audit_path,
                allowed_prefixes=("artifacts",),
                expected_name="audit.jsonl",
            )
        except ArtifactPathError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        return OpsSummaryResponse(
            eval=summarize_eval_artifacts(
                safe_eval_dir,
                input_cost_per_1k=input_cost_per_1k,
                output_cost_per_1k=output_cost_per_1k,
            ),
            tools=summarize_audit_log(safe_audit_path),
        )

    return app


app = create_app()
