from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from ..providers import LANE_OFFLINE, normalize_lane, require_openai_key
from .state import RouteKind


@dataclass(frozen=True)
class RouteDecision:
    route: RouteKind
    save_requested: bool
    tool_args: dict[str, Any] = field(default_factory=dict)


class Router(Protocol):
    def route(self, question: str) -> RouteDecision: ...


class QueryRewriter(Protocol):
    def rewrite(self, question: str, attempt: int) -> str: ...


_SAVE_MARKERS = ("저장", "보고서로", "리포트로", "파일로")
_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
_TOP_N_RE = re.compile(r"(\d+)\s*[건개]")
_EOK_GTE_RE = re.compile(r"(\d+)\s*억\s*(?:원)?\s*이상")
_ISSUER_RE = re.compile(r"([0-9A-Za-z가-힣]+)(?:이|가)\s*발주한")
_COUNT_MARKERS = ("몇 건", "몇건", "몇 개", "몇개", "건수")
_SUM_MARKERS = ("합계", "총액", "총 금액", "총금액")
_BUDGET_MARKERS = ("금액", "예산", "사업비")
_DESC_MARKERS = ("가장 큰", "가장 많은", "가장 높은", "최대")
_DEADLINE_ASC_MARKERS = ("마감이 가장 빠른", "마감이 빠른", "마감 임박")


def _extract_tool_args(q: str) -> dict[str, Any] | None:
    """집계/정렬/건수 패턴이면 aggregate_metadata 인자, 아니면 None (→ rag_query)."""
    args: dict[str, Any] = {}
    filters: list[dict[str, Any]] = []

    m = _ISSUER_RE.search(q)
    if m:
        filters.append({"field": "issuer", "op": "contains", "value": m.group(1)})
    m = _EOK_GTE_RE.search(q)
    if m:
        filters.append({"field": "budget_krw_int", "op": "gte", "value": int(m.group(1)) * 100_000_000})

    is_count = any(k in q for k in _COUNT_MARKERS)
    is_sum = any(k in q for k in _SUM_MARKERS) and any(k in q for k in _BUDGET_MARKERS)
    sort_desc_budget = any(k in q for k in _DESC_MARKERS) and any(k in q for k in _BUDGET_MARKERS)
    sort_asc_deadline = any(k in q for k in _DEADLINE_ASC_MARKERS)

    if not (is_count or is_sum or sort_desc_budget or sort_asc_deadline):
        return None

    if filters:
        args["filters"] = filters
    if is_count:
        args["agg"] = "count"
    elif is_sum:
        args["agg"] = "sum"
        args["agg_field"] = "budget_krw_int"
    else:
        args["agg"] = "list"
        if sort_desc_budget:
            args["sort_by"] = "budget_krw_int"
            args["descending"] = True
        else:
            args["sort_by"] = "bid_end_at_iso"
            args["descending"] = False
        m = _TOP_N_RE.search(q)
        args["top_n"] = int(m.group(1)) if m else 5
    return args


class RuleRouter:
    """Offline deterministic router: 집계 패턴 → metadata_query, 그 외 → rag_query."""

    def route(self, question: str) -> RouteDecision:
        q = question or ""
        save = any(k in q for k in _SAVE_MARKERS)
        tool_args = _extract_tool_args(q)
        if tool_args is not None:
            return RouteDecision("metadata_query", save, tool_args)
        return RouteDecision("rag_query", save)


_STOPWORDS = {
    "안녕하세요", "혹시", "궁금한데요", "궁금한데", "궁금해요", "그게", "다른", "말고",
    "알려줘", "알려주세요", "있을까요", "대해", "대해서", "관련해서", "관련", "좀",
    "그리고", "그러면", "근데", "그런데", "혹은", "아니면", "뭐야", "뭔가요", "무엇인가요",
}


class RuleQueryRewriter:
    """Offline deterministic rewriter: 불용어 제거 → (attempt≥2) 3글자 미만 토큰 제거."""

    def rewrite(self, question: str, attempt: int) -> str:
        tokens = _TOKEN_RE.findall(question or "")
        kept = [t for t in tokens if t not in _STOPWORDS and len(t) >= 2]
        if attempt >= 2:
            kept = [t for t in kept if len(t) >= 3]
        return " ".join(kept) or question


class _MetadataFilterPayload(BaseModel):
    field: Literal["issuer", "budget_krw_int", "bid_end_at_iso", "project_name", "notice_number"]
    op: Literal["eq", "contains", "gte", "lte"]
    value: str | int


class RoutePayload(BaseModel):
    route: Literal["rag_query", "metadata_query"] = Field(description="질문 유형")
    save_requested: bool = Field(default=False, description="보고서 저장 요청 여부")
    filters: list[_MetadataFilterPayload] = Field(default_factory=list)
    sort_by: Literal["budget_krw_int", "bid_end_at_iso", "published_at_iso"] | None = None
    descending: bool = True
    top_n: int = 5
    agg: Literal["list", "count", "sum"] = "list"
    agg_field: Literal["budget_krw_int"] | None = None


_ROUTER_SYSTEM_PROMPT = (
    "당신은 RFP 검색 시스템의 질의 라우터입니다. 질문을 분류하세요. "
    "corpus 전체에 대한 정렬·필터·건수·합계 질문(예: '예산이 가장 큰 3건', '몇 건', '합계')은 "
    "metadata_query로, 특정 공고 내용에 대한 질문은 rag_query로 분류합니다. "
    "metadata_query면 filters/sort_by/top_n/agg 인자를 채우세요. "
    "질문에 결과를 보고서·파일로 저장하라는 요청이 있으면 save_requested를 true로 하세요."
)


class LLMRouter:
    """Real lane router: ChatOpenAI structured output."""

    def __init__(self, invoke=None) -> None:
        self._invoke = invoke or self._default_invoke

    @staticmethod
    def _default_invoke(question: str) -> RoutePayload:
        from langchain_openai import ChatOpenAI

        model = os.environ.get("RFP_GENERATION_MODEL", "gpt-5.4-mini")
        llm = ChatOpenAI(model=model).with_structured_output(RoutePayload)
        return llm.invoke([("system", _ROUTER_SYSTEM_PROMPT), ("human", question)])

    def route(self, question: str) -> RouteDecision:
        p = self._invoke(question)
        if p.route == "rag_query":
            return RouteDecision("rag_query", p.save_requested)
        args: dict[str, Any] = {"agg": p.agg}
        if p.filters:
            args["filters"] = [f.model_dump() for f in p.filters]
        if p.agg == "sum":
            args["agg_field"] = p.agg_field or "budget_krw_int"
        if p.agg == "list":
            args["sort_by"] = p.sort_by or "budget_krw_int"
            args["descending"] = p.descending
            args["top_n"] = p.top_n
        return RouteDecision("metadata_query", p.save_requested, args)


_REWRITER_SYSTEM_PROMPT = (
    "당신은 RFP 검색 질의 재작성기입니다. 검색에 실패한 질문에서 잡담·불용어를 제거하고 "
    "핵심 키워드(사업명, 기관명, 묻는 항목)만 남긴 검색 질의 한 줄을 출력하세요."
)


class _RewritePayload(BaseModel):
    query: str = Field(description="재작성된 검색 질의")


class LLMQueryRewriter:
    """Real lane rewriter: ChatOpenAI structured output."""

    def __init__(self, invoke=None) -> None:
        self._invoke = invoke or self._default_invoke

    @staticmethod
    def _default_invoke(question: str) -> _RewritePayload:
        from langchain_openai import ChatOpenAI

        model = os.environ.get("RFP_GENERATION_MODEL", "gpt-5.4-mini")
        llm = ChatOpenAI(model=model).with_structured_output(_RewritePayload)
        return llm.invoke([("system", _REWRITER_SYSTEM_PROMPT), ("human", question)])

    def rewrite(self, question: str, attempt: int) -> str:
        return self._invoke(question).query or question


def build_router(lane: str) -> Router:
    if normalize_lane(lane) == LANE_OFFLINE:
        return RuleRouter()
    require_openai_key()
    return LLMRouter()


def build_rewriter(lane: str) -> QueryRewriter:
    if normalize_lane(lane) == LANE_OFFLINE:
        return RuleQueryRewriter()
    require_openai_key()
    return LLMQueryRewriter()
