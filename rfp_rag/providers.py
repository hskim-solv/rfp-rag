from __future__ import annotations

import hashlib
import math
from typing import Protocol

from langchain_core.embeddings import Embeddings

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
    """Generates the answer string for a query given retrieved chunks."""

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
