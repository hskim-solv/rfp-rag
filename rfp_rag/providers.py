from __future__ import annotations

import hashlib
import math
import os
from typing import Callable, Protocol

from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, Field

from .fake_provider import lexical_features
from .index_store import SearchResult


class LexicalHashEmbeddings(Embeddings):
    """Deterministic offline embeddings: hashed Korean n-gram lexical features.

    Cosine similarity approximates the legacy fake lexical retrieval, so the
    offline lane keeps meaningful retrieval/abstention behavior without API keys.
    """

    def __init__(self, dim: int = 4096) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for feature, weight in lexical_features(text).items():
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dim
            # signed hashing trick: collisions cancel in expectation
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign * float(weight)
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            vec[0] = 1.0
            return vec
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class AnswerGenerator(Protocol):
    """Generates the answer string for a query given retrieved chunks.

    Contract: ``results`` MUST be non-empty. Callers gate empty/low-score
    retrieval before calling (see ``rag_chain.answer_with_store``).
    """

    def generate(self, query: str, results: list[SearchResult]) -> str: ...


class TemplateAnswerGenerator:
    """Offline deterministic generator: metadata template with context fallback."""

    def generate(self, query: str, results: list[SearchResult]) -> str:
        top = results[0]
        return self._metadata_answer(query, top) or self._context_answer(top)

    @staticmethod
    def _metadata_answer(query: str, top: SearchResult) -> str | None:
        md = top.metadata
        query_text = query or ""
        project = md.get("project_name", "해당 사업")
        if "예산" in query_text or "금액" in query_text or "사업비" in query_text:
            value = md.get("budget_krw_int")
            if value is not None:
                return f"{project}의 사업 금액은 {value:,}원입니다."
        if "마감" in query_text or "기한" in query_text or "입찰" in query_text:
            value = md.get("bid_end_at_iso") or md.get("bid_end_at_raw")
            if value:
                return f"{project}의 입찰 참여 마감일은 {value}입니다."
        if "발주" in query_text or "기관" in query_text:
            value = md.get("issuer")
            if value:
                return f"{project}의 발주 기관은 {value}입니다."
        if "요약" in query_text or "무엇" in query_text or "내용" in query_text:
            summary = (md.get("summary") or "").strip()
            if summary:
                return f"{project} 요약: {summary}"
        return None

    @staticmethod
    def _context_answer(top: SearchResult) -> str:
        md = top.metadata
        project = md.get("project_name", "검색된 사업")
        issuer = md.get("issuer", "발주기관 미상")
        summary = (md.get("summary") or "").strip()
        if summary:
            return f"검색된 근거 기준으로 {project}는 {issuer}의 사업이며, 주요 내용은 다음과 같습니다. {summary}"
        snippet = " ".join((top.text or "").split())[:350]
        return f"검색된 근거 기준으로 {project}는 {issuer}의 사업입니다. 관련 본문: {snippet}"


SYSTEM_PROMPT = (
    "당신은 B2G 입찰지원 컨설팅 '입찰메이트'의 RFP 분석 어시스턴트입니다. "
    "반드시 아래 제공된 근거 chunk 내용만 사용해 한국어로 답하세요. "
    "모든 답변은 근거가 된 chunk id를 cited_chunk_ids에 담으세요. "
    "근거가 부족하면 insufficient_context를 true로 하고 answer에 '없는 정보'를 포함하세요. "
    "금액·날짜·기관명은 근거 원문 표기 그대로 인용하세요."
)


class LLMAnswer(BaseModel):
    answer: str = Field(description="근거 기반 한국어 답변")
    cited_chunk_ids: list[str] = Field(default_factory=list, description="답변 근거 chunk id 목록")
    insufficient_context: bool = Field(default=False, description="근거 부족 여부")


def build_answer_prompt(query: str, results: list[SearchResult]) -> str:
    blocks = []
    for r in results:
        blocks.append(f"[{r.chunk_id}] (사업명: {r.metadata.get('project_name', '')})\n{r.text}")
    context = "\n\n".join(blocks)
    return f"근거 chunk 목록:\n\n{context}\n\n질문: {query}"


def _default_invoke(prompt: str) -> LLMAnswer:
    from langchain_openai import ChatOpenAI

    model = os.environ.get("RFP_GENERATION_MODEL", "gpt-5.4-mini")
    llm = ChatOpenAI(model=model).with_structured_output(LLMAnswer)
    return llm.invoke([("system", SYSTEM_PROMPT), ("human", prompt)])


class LLMAnswerGenerator:
    """Real lane generator: ChatOpenAI structured output with citation validation."""

    def __init__(self, invoke: Callable[[str], LLMAnswer] | None = None) -> None:
        self._invoke = invoke or _default_invoke
        self.last_cited_chunk_ids: list[str] = []

    def generate(self, query: str, results: list[SearchResult]) -> str:
        payload = self._invoke(build_answer_prompt(query, results))
        retrieved_ids = {r.chunk_id for r in results}
        self.last_cited_chunk_ids = [cid for cid in payload.cited_chunk_ids if cid in retrieved_ids]
        if payload.insufficient_context:
            answer = payload.answer or ""
            return answer if "없는 정보" in answer else f"{answer} 없는 정보".strip()
        return payload.answer


LANE_OFFLINE = "offline"
LANE_REAL_OPENAI = "real_openai"

_LANE_ALIASES = {
    "offline": LANE_OFFLINE,
    "fake": LANE_OFFLINE,
    "fake_offline": LANE_OFFLINE,
    "openai": LANE_REAL_OPENAI,
    "real_openai": LANE_REAL_OPENAI,
}

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


def normalize_lane(value: str) -> str:
    lane = _LANE_ALIASES.get((value or "").strip().lower())
    if lane is None:
        raise ValueError(f"unknown lane: {value!r} (expected one of {sorted(_LANE_ALIASES)})")
    return lane


def require_openai_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY required for real lane (offline lane runs without credentials)"
        )


def embedding_model_name(lane: str) -> str:
    if lane == LANE_OFFLINE:
        return "lexical-hash-v1"
    return os.environ.get("RFP_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def build_embeddings(lane: str):
    if lane == LANE_OFFLINE:
        return LexicalHashEmbeddings()
    require_openai_key()
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(model=embedding_model_name(lane))


def build_generator(lane: str) -> AnswerGenerator:
    if lane == LANE_OFFLINE:
        return TemplateAnswerGenerator()
    require_openai_key()
    return LLMAnswerGenerator()
