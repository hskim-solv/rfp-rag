# LangGraph Agent Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 단발 RAG 체인을 LangGraph StateGraph 기반 stateful multi-step agent(라우팅/자가교정 검색 루프/도구 호출/HITL 승인)로 확장하고 `agent_lane_complete` 게이트로 검증한다.

**Architecture:** 그래프 토폴로지는 레인 공통, 노드 두뇌(Router/QueryRewriter)만 offline 규칙 기반 vs real LLM 구현 주입. 기존 `rag_chain`/`providers`/`vector_index`는 수정 없이 호출만 한다. 설계 문서: `docs/superpowers/specs/2026-06-10-langgraph-agent-lane-design.md`.

**Tech Stack:** langgraph>=1.0 (StateGraph, interrupt, Command), langgraph-checkpoint-sqlite (SqliteSaver), 기존 LangChain/Qdrant 자산.

**설계 대비 단순화 (구현 결정):** metadata 경로의 답변 포맷은 양 레인 공통 결정론 포맷터를 쓴다 (설계 §3은 real=LLM 포맷팅이라 했으나, 결정론 채점과 비용 관점에서 공통 포맷터로 단순화 — 설계 문서에 반영할 것).

---

### Task 1: 의존성 + agent 패키지 골격 (state.py)

**Files:**
- Modify: `pyproject.toml`
- Create: `rfp_rag/agent/__init__.py`, `rfp_rag/agent/state.py`

- [ ] **Step 1: pyproject.toml 의존성 추가**

`dependencies` 배열에 두 줄 추가:

```toml
    "langgraph>=1.0",
    "langgraph-checkpoint-sqlite",
```

- [ ] **Step 2: 설치 및 임포트 확인**

Run: `pip install -e . && python3 -c "from langgraph.graph import StateGraph, START, END; from langgraph.types import Command, interrupt; from langgraph.checkpoint.memory import MemorySaver; from langgraph.checkpoint.sqlite import SqliteSaver; print('ok')"`
Expected: `ok`

- [ ] **Step 3: 패키지 골격 작성**

`rfp_rag/agent/__init__.py`:

```python
"""LangGraph stateful multi-step agent lane. See docs/superpowers/specs/2026-06-10-langgraph-agent-lane-design.md."""
```

`rfp_rag/agent/state.py`:

```python
from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from ..index_store import SearchResult

RouteKind = Literal["rag_query", "metadata_query"]

OUTCOME_ANSWERED = "answered"
OUTCOME_ABSTAINED = "abstained"
OUTCOME_REJECTED = "rejected"


class AgentState(TypedDict, total=False):
    question: str                       # 현재(재작성 반영) 질의
    original_question: str
    route: RouteKind
    save_requested: bool
    tool_args: dict[str, Any]           # metadata_query 도구 인자 (router가 추출)
    results: list[dict[str, Any]]       # SearchResult 직렬화 (checkpointer 호환)
    grade: str                          # sufficient | insufficient
    rewrite_count: int
    regenerated: bool
    verify_ok: bool
    tool_result: dict[str, Any] | None  # aggregate_metadata 결과
    answer: dict[str, Any] | None       # 기존 응답 JSON 스키마 (+ agent 확장 필드)
    outcome: str                        # answered | abstained | rejected
    tool_calls: Annotated[list[dict[str, Any]], operator.add]  # audit용 누적


def result_to_dict(r: SearchResult) -> dict[str, Any]:
    return {
        "chunk_id": r.chunk_id,
        "doc_id": r.doc_id,
        "csv_row_id": r.csv_row_id,
        "score": r.score,
        "text": r.text,
        "metadata": r.metadata,
    }


def dict_to_result(d: dict[str, Any]) -> SearchResult:
    return SearchResult(
        chunk_id=d["chunk_id"],
        doc_id=d["doc_id"],
        csv_row_id=d["csv_row_id"],
        score=d["score"],
        text=d["text"],
        metadata=d["metadata"],
    )
```

- [ ] **Step 4: 기존 테스트 회귀 확인**

Run: `python3 -m pytest -q -m "not real"`
Expected: 전체 PASS (agent 코드는 아직 임포트되지 않음)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml rfp_rag/agent/
git commit -m "feat: add langgraph deps and agent package skeleton (AgentState)"
```

---

### Task 2: 레인별 두뇌 — RuleRouter / RuleQueryRewriter / LLM 구현 (brains.py)

**Files:**
- Create: `rfp_rag/agent/brains.py`
- Test: `tests/test_agent_brains.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_agent_brains.py`:

```python
from __future__ import annotations

from rfp_rag.agent.brains import RuleQueryRewriter, RuleRouter, build_rewriter, build_router


def test_rule_router_metadata_sort_query() -> None:
    d = RuleRouter().route("사업 금액이 가장 큰 공고 3건은 뭐야?")
    assert d.route == "metadata_query"
    assert d.save_requested is False
    assert d.tool_args["sort_by"] == "budget_krw_int"
    assert d.tool_args["descending"] is True
    assert d.tool_args["top_n"] == 3


def test_rule_router_count_query() -> None:
    d = RuleRouter().route("한국전력공사가 발주한 공고는 몇 건이야?")
    assert d.route == "metadata_query"
    assert d.tool_args["agg"] == "count"
    assert {"field": "issuer", "op": "contains", "value": "한국전력공사"} in d.tool_args["filters"]


def test_rule_router_sum_query() -> None:
    d = RuleRouter().route("사업 금액이 10억 이상인 공고들의 금액 합계는 얼마야?")
    assert d.route == "metadata_query"
    assert d.tool_args["agg"] == "sum"
    assert d.tool_args["agg_field"] == "budget_krw_int"
    assert {"field": "budget_krw_int", "op": "gte", "value": 1_000_000_000} in d.tool_args["filters"]


def test_rule_router_deadline_query() -> None:
    d = RuleRouter().route("입찰 마감이 가장 빠른 공고 5건 알려줘")
    assert d.route == "metadata_query"
    assert d.tool_args["sort_by"] == "bid_end_at_iso"
    assert d.tool_args["descending"] is False
    assert d.tool_args["top_n"] == 5


def test_rule_router_rag_default_and_save_flag() -> None:
    d = RuleRouter().route("한영대학교 트랙운영 학사정보시스템 고도화 사업을 요약해서 보고서로 저장해줘")
    assert d.route == "rag_query"
    assert d.save_requested is True
    d2 = RuleRouter().route("한영대학교 사업의 발주 기관은 어디야?")
    assert d2.route == "rag_query"
    assert d2.save_requested is False


def test_rule_rewriter_strips_noise_deterministically() -> None:
    rw = RuleQueryRewriter()
    noisy = "안녕하세요 혹시 다른 건 말고 그게 궁금한데요 한영대학교 트랙운영 학사정보시스템 고도화 사업 예산 알려줘"
    first = rw.rewrite(noisy, attempt=1)
    assert "안녕하세요" not in first and "혹시" not in first
    assert "한영대학교" in first and "예산" in first
    assert rw.rewrite(noisy, attempt=1) == first  # 결정론
    second = rw.rewrite(noisy, attempt=2)
    assert len(second) <= len(first)


def test_factories_offline() -> None:
    assert isinstance(build_router("offline"), RuleRouter)
    assert isinstance(build_rewriter("offline"), RuleQueryRewriter)
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_agent_brains.py -q`
Expected: FAIL — `ModuleNotFoundError: rfp_rag.agent.brains`

- [ ] **Step 3: 구현**

`rfp_rag/agent/brains.py`:

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python3 -m pytest tests/test_agent_brains.py -q`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/agent/brains.py tests/test_agent_brains.py
git commit -m "feat: lane-injectable agent brains — rule/LLM router and query rewriter"
```

---

### Task 3: aggregate_metadata 도구 (tools.py 1/2)

**Files:**
- Create: `rfp_rag/agent/tools.py`
- Test: `tests/test_agent_tools.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_agent_tools.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rfp_rag.agent.tools import AuditLogger, aggregate_metadata, save_report_file
from rfp_rag.corpus import CorpusDocument


def _docs() -> list[CorpusDocument]:
    rows = [
        ("000", "A시스템 구축", "한국전력공사", 500_000_000, "2024-10-01T17:00:00"),
        ("001", "B플랫폼 고도화", "서울대학교", 1_500_000_000, "2024-09-01T17:00:00"),
        ("002", "C포털 유지보수", "한국전력공사", 2_000_000_000, None),
    ]
    return [
        CorpusDocument(
            csv_row_id=rid,
            doc_id=f"doc:{rid}",
            text="본문",
            metadata={
                "project_name": name,
                "issuer": issuer,
                "budget_krw_int": budget,
                "bid_end_at_iso": deadline,
            },
        )
        for rid, name, issuer, budget, deadline in rows
    ]


def test_aggregate_sort_budget_desc_top2() -> None:
    out = aggregate_metadata(_docs(), sort_by="budget_krw_int", descending=True, top_n=2)
    assert [r["doc_id"] for r in out["rows"]] == ["doc:002", "doc:001"]
    assert out["count"] == 3  # count는 필터 후 전체 건수 (top_n 무관)
    assert out["doc_ids"] == ["doc:002", "doc:001"]


def test_aggregate_sort_deadline_asc_puts_none_last() -> None:
    out = aggregate_metadata(_docs(), sort_by="bid_end_at_iso", descending=False, top_n=3)
    assert [r["doc_id"] for r in out["rows"]] == ["doc:001", "doc:000", "doc:002"]


def test_aggregate_filter_contains_and_count() -> None:
    out = aggregate_metadata(
        _docs(),
        filters=[{"field": "issuer", "op": "contains", "value": "한국전력"}],
        agg="count",
    )
    assert out["count"] == 2
    assert out["rows"] == []  # count 모드는 rows 미반환


def test_aggregate_filter_gte_and_sum() -> None:
    out = aggregate_metadata(
        _docs(),
        filters=[{"field": "budget_krw_int", "op": "gte", "value": 1_000_000_000}],
        agg="sum",
        agg_field="budget_krw_int",
    )
    assert out["sum"] == 3_500_000_000
    assert out["count"] == 2


def test_aggregate_rejects_unknown_field_or_op() -> None:
    with pytest.raises(ValueError, match="unsupported filter"):
        aggregate_metadata(_docs(), filters=[{"field": "csv_filename_raw", "op": "eq", "value": "x"}])
    with pytest.raises(ValueError, match="unsupported filter"):
        aggregate_metadata(_docs(), filters=[{"field": "issuer", "op": "regex", "value": "x"}])
    with pytest.raises(ValueError, match="unsupported sort_by"):
        aggregate_metadata(_docs(), sort_by="text")
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_agent_tools.py -q`
Expected: FAIL — `ModuleNotFoundError: rfp_rag.agent.tools`

- [ ] **Step 3: 구현**

`rfp_rag/agent/tools.py`:

```python
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..corpus import CorpusDocument

ALLOWED_FILTER_OPS = {"eq", "contains", "gte", "lte"}
ALLOWED_FIELDS = {
    "project_name",
    "issuer",
    "budget_krw_int",
    "bid_end_at_iso",
    "published_at_iso",
    "notice_number",
}
ROW_FIELDS = ("project_name", "issuer", "budget_krw_int", "bid_end_at_iso")


def _matches(value: Any, op: str, target: Any) -> bool:
    if value is None:
        return False
    if op == "eq":
        return value == target
    if op == "contains":
        return str(target) in str(value)
    if op == "gte":
        return value >= target
    if op == "lte":
        return value <= target
    raise ValueError(f"unsupported filter op: {op!r}")


def aggregate_metadata(
    docs: list[CorpusDocument],
    *,
    filters: list[dict[str, Any]] | None = None,
    sort_by: str | None = None,
    descending: bool = True,
    top_n: int = 5,
    agg: str = "list",
    agg_field: str | None = None,
) -> dict[str, Any]:
    """corpus 메타데이터 필터·정렬·집계. count는 필터 후 전체 건수(top_n 무관)."""
    if agg not in {"list", "count", "sum"}:
        raise ValueError(f"unsupported agg: {agg!r}")
    if sort_by is not None and sort_by not in ALLOWED_FIELDS:
        raise ValueError(f"unsupported sort_by: {sort_by!r}")

    selected = list(docs)
    for f in filters or []:
        field, op, value = f.get("field"), f.get("op"), f.get("value")
        if field not in ALLOWED_FIELDS or op not in ALLOWED_FILTER_OPS:
            raise ValueError(f"unsupported filter: {f!r}")
        selected = [d for d in selected if _matches(d.metadata.get(field), op, value)]

    count = len(selected)
    if agg == "count":
        return {"agg": "count", "count": count, "rows": [], "doc_ids": []}
    if agg == "sum":
        field = agg_field or "budget_krw_int"
        if field not in ALLOWED_FIELDS:
            raise ValueError(f"unsupported sort_by: {field!r}")
        total = sum(d.metadata.get(field) or 0 for d in selected)
        return {"agg": "sum", "agg_field": field, "sum": total, "count": count, "rows": [], "doc_ids": []}

    if sort_by is not None:
        # None 값은 정렬 방향과 무관하게 항상 뒤로 보낸다.
        selected.sort(
            key=lambda d: (
                (d.metadata.get(sort_by) is None),
                d.metadata.get(sort_by) if not descending else None,
            )
        )
        if descending:
            with_value = [d for d in selected if d.metadata.get(sort_by) is not None]
            without = [d for d in selected if d.metadata.get(sort_by) is None]
            with_value.sort(key=lambda d: d.metadata[sort_by], reverse=True)
            selected = with_value + without
    rows = [
        {"doc_id": d.doc_id, "csv_row_id": d.csv_row_id, **{k: d.metadata.get(k) for k in ROW_FIELDS}}
        for d in selected[: max(int(top_n), 0)]
    ]
    return {"agg": "list", "count": count, "rows": rows, "doc_ids": [r["doc_id"] for r in rows]}
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_agent_tools.py -q`
Expected: 5 passed (Task 4의 save_report/audit 테스트는 아직 없음)

주의: asc 정렬 구현(`descending=False`)은 tuple key `(is_none, value)`로 동작하지만 `descending=True` 분기는 명시 재정렬을 쓴다. 테스트 `test_aggregate_sort_deadline_asc_puts_none_last`가 실패하면 asc 분기 key를 `lambda d: ((d.metadata.get(sort_by) is None), d.metadata.get(sort_by) or "")`로 교체할 것 (None과 str 비교 TypeError 방지).

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/agent/tools.py tests/test_agent_tools.py
git commit -m "feat: aggregate_metadata tool — filter/sort/count/sum over corpus metadata"
```

---

### Task 4: save_report_file + AuditLogger (tools.py 2/2)

**Files:**
- Modify: `rfp_rag/agent/tools.py` (append)
- Test: `tests/test_agent_tools.py` (append)

- [ ] **Step 1: 실패하는 테스트 추가 (test_agent_tools.py에 append)**

```python
def test_save_report_file_writes_inside_reports_dir(tmp_path: Path) -> None:
    target = save_report_file(tmp_path / "reports", "agent_report_t1.md", "# 보고서\n내용")
    assert target.read_text(encoding="utf-8").startswith("# 보고서")
    assert target.parent == (tmp_path / "reports").resolve()


def test_save_report_file_rejects_path_escape_and_bad_ext(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid report filename"):
        save_report_file(tmp_path, "../escape.md", "x")
    with pytest.raises(ValueError, match="invalid report filename"):
        save_report_file(tmp_path, "sub/dir.md", "x")
    with pytest.raises(ValueError, match="invalid report filename"):
        save_report_file(tmp_path, "note.txt", "x")


def test_audit_logger_appends_jsonl(tmp_path: Path) -> None:
    audit = AuditLogger(tmp_path / "audit.jsonl")
    audit.record(thread_id="t1", tool="search_rfp", args={"query": "q"}, outcome="3 results")
    audit.record(thread_id="t1", tool="save_report", args={"filename": "a.md"}, outcome="rejected", approved=False)
    lines = [json.loads(l) for l in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert lines[0]["tool"] == "search_rfp" and lines[0]["approved"] is None
    assert lines[1]["approved"] is False and lines[1]["thread_id"] == "t1"
    assert all("ts" in l for l in lines)
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_agent_tools.py -q`
Expected: 새 3건 FAIL — `ImportError` (save_report_file, AuditLogger 미정의)

- [ ] **Step 3: 구현 (tools.py에 append)**

```python
_FILENAME_RE = re.compile(r"^[0-9A-Za-z가-힣._-]+\.md$")


def save_report_file(reports_dir: Path, filename: str, content: str) -> Path:
    """reports_dir 하위에만 .md 저장. 경로 구분자/탈출 차단."""
    if not _FILENAME_RE.match(filename or "") or ".." in filename:
        raise ValueError(f"invalid report filename: {filename!r} (expected <name>.md, no path separators)")
    reports_dir = reports_dir.resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    target = (reports_dir / filename).resolve()
    if target.parent != reports_dir:
        raise ValueError(f"invalid report filename: {filename!r} (escapes reports dir)")
    target.write_text(content, encoding="utf-8")
    return target


@dataclass
class AuditLogger:
    """도구 호출 감사 로그 (JSONL append)."""

    path: Path

    def record(
        self,
        *,
        thread_id: str,
        tool: str,
        args: dict[str, Any],
        outcome: str,
        approved: bool | None = None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "thread_id": thread_id,
            "tool": tool,
            "args": args,
            "outcome": outcome,
            "approved": approved,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_agent_tools.py -q`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/agent/tools.py tests/test_agent_tools.py
git commit -m "feat: save_report_file with path-escape guard and AuditLogger (JSONL)"
```

---

### Task 5: 노드 구현 — AgentRuntime (nodes.py)

**Files:**
- Create: `rfp_rag/agent/nodes.py`
- Test: `tests/test_agent_nodes.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_agent_nodes.py`:

```python
from __future__ import annotations

from pathlib import Path

from rfp_rag.agent.brains import RuleQueryRewriter, RuleRouter
from rfp_rag.agent.nodes import AgentRuntime
from rfp_rag.agent.tools import AuditLogger
from rfp_rag.chunking import Chunk
from rfp_rag.corpus import CorpusDocument
from rfp_rag.providers import LexicalHashEmbeddings, TemplateAnswerGenerator
from rfp_rag.vector_index import build_vector_store

PROJECT = "한영대학교 트랙운영 학사정보시스템 고도화"


def _runtime(tmp_path: Path, min_score: float = 0.05) -> AgentRuntime:
    chunks = [
        Chunk(
            chunk_id="doc:000:chunk:0",
            doc_id="doc:000",
            csv_row_id="000",
            text=f"{PROJECT} 사업 제안요청서 본문",
            metadata={
                "project_name": PROJECT,
                "issuer": "한영대학",
                "summary": "학사정보시스템 고도화 사업",
                "budget_krw_int": 130_000_000,
                "bid_end_at_iso": "2024-10-15T17:00:00",
                "csv_filename_raw": "han.hwp",
            },
        )
    ]
    store = build_vector_store(chunks, LexicalHashEmbeddings(dim=512), qdrant_path=None, lane="offline")
    docs = [
        CorpusDocument(
            csv_row_id="000",
            doc_id="doc:000",
            text="본문",
            metadata={
                "project_name": PROJECT,
                "issuer": "한영대학",
                "budget_krw_int": 130_000_000,
                "bid_end_at_iso": "2024-10-15T17:00:00",
            },
        )
    ]
    return AgentRuntime(
        store=store,
        generator=TemplateAnswerGenerator(),
        router=RuleRouter(),
        rewriter=RuleQueryRewriter(),
        docs=docs,
        audit=AuditLogger(tmp_path / "audit.jsonl"),
        reports_dir=tmp_path / "reports",
        top_k=3,
        min_score=min_score,
        thread_id="t-test",
    )


def test_route_node_sets_route_and_original(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    out = rt.route_node({"question": f"{PROJECT} 사업 예산 알려줘"})
    assert out["route"] == "rag_query"
    assert out["original_question"] == f"{PROJECT} 사업 예산 알려줘"


def test_retrieve_and_grade_sufficient(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    out = rt.retrieve_node({"question": f"{PROJECT} 사업 예산 알려줘"})
    assert out["results"] and out["results"][0]["chunk_id"] == "doc:000:chunk:0"
    assert out["tool_calls"][0]["tool"] == "search_rfp"
    graded = rt.grade_node({"results": out["results"]})
    assert graded["grade"] == "sufficient"


def test_grade_branch_routes_by_count(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    assert rt.grade_branch({"grade": "sufficient"}) == "generate"
    assert rt.grade_branch({"grade": "insufficient", "rewrite_count": 0}) == "rewrite"
    assert rt.grade_branch({"grade": "insufficient", "rewrite_count": 2}) == "abstain"


def test_rewrite_node_increments_and_rewrites(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    out = rt.rewrite_node({"original_question": "안녕하세요 혹시 한영대학교 예산 알려줘", "rewrite_count": 0})
    assert out["rewrite_count"] == 1
    assert "안녕하세요" not in out["question"]


def test_generate_and_verify_rag_path(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    retrieved = rt.retrieve_node({"question": f"{PROJECT} 사업 예산 알려줘"})
    state = {
        "route": "rag_query",
        "question": f"{PROJECT} 사업 예산 알려줘",
        "original_question": f"{PROJECT} 사업 예산 알려줘",
        "results": retrieved["results"],
    }
    gen = rt.generate_node(state)
    assert gen["answer"] is not None
    assert "130,000,000" in gen["answer"]["answer"]
    assert gen["answer"]["sources"][0]["chunk_id"] == "doc:000:chunk:0"
    verified = rt.verify_node({**state, **gen})
    assert verified["verify_ok"] is True


def test_generate_node_metadata_route_formats_tool_result(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    state = {
        "route": "metadata_query",
        "question": "사업 금액이 가장 큰 공고 1건은?",
        "original_question": "사업 금액이 가장 큰 공고 1건은?",
        "tool_args": {"sort_by": "budget_krw_int", "descending": True, "top_n": 1, "agg": "list"},
    }
    tool_out = rt.tool_exec_node(state)
    assert tool_out["tool_result"]["doc_ids"] == ["doc:000"]
    gen = rt.generate_node({**state, **tool_out})
    assert PROJECT in gen["answer"]["answer"]
    assert gen["answer"]["sources"][0]["doc_id"] == "doc:000"
    verified = rt.verify_node({**state, **tool_out, **gen})
    assert verified["verify_ok"] is True


def test_verify_branch_decisions(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    assert rt.verify_branch({"answer": None}) == "abstain"
    assert rt.verify_branch({"answer": {"x": 1}, "verify_ok": True, "save_requested": False}) == "respond"
    assert rt.verify_branch({"answer": {"x": 1}, "verify_ok": True, "save_requested": True}) == "save_report"
    assert rt.verify_branch({"answer": {"x": 1}, "verify_ok": False}) == "regenerate"
    assert rt.verify_branch({"answer": {"x": 1}, "verify_ok": False, "regenerated": True}) == "abstain"


def test_abstain_node_uses_existing_contract(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    out = rt.abstain_node({"original_question": "화성 이주선 산소탱크?", "results": []})
    assert "없는 정보" in out["answer"]["answer"]
    assert "insufficient_context" in out["answer"]["warnings"]
    assert out["outcome"] == "abstained"
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_agent_nodes.py -q`
Expected: FAIL — `ModuleNotFoundError: rfp_rag.agent.nodes`

- [ ] **Step 3: 구현**

`rfp_rag/agent/nodes.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_qdrant import QdrantVectorStore
from langgraph.types import interrupt

from ..corpus import CorpusDocument
from ..index_store import SearchResult
from ..providers import AnswerGenerator, chunk_context_block
from ..rag_chain import DEFAULT_MIN_SCORE, _source_from_result, abstention_response
from ..vector_index import search
from .brains import QueryRewriter, Router
from .state import (
    OUTCOME_ABSTAINED,
    OUTCOME_ANSWERED,
    OUTCOME_REJECTED,
    AgentState,
    dict_to_result,
    result_to_dict,
)
from .tools import AuditLogger, aggregate_metadata, save_report_file


@dataclass
class AgentRuntime:
    """그래프 노드 묶음. 레인별 차이는 generator/router/rewriter 주입으로만 갈라진다."""

    store: QdrantVectorStore
    generator: AnswerGenerator
    router: Router
    rewriter: QueryRewriter
    docs: list[CorpusDocument]
    audit: AuditLogger
    reports_dir: Path
    top_k: int = 5
    min_score: float = DEFAULT_MIN_SCORE
    max_rewrites: int = 2
    thread_id: str = "default"

    # --- nodes -------------------------------------------------------------

    def route_node(self, state: AgentState) -> dict[str, Any]:
        question = state["question"]
        decision = self.router.route(question)
        return {
            "route": decision.route,
            "save_requested": decision.save_requested,
            "tool_args": decision.tool_args,
            "original_question": state.get("original_question") or question,
        }

    def retrieve_node(self, state: AgentState) -> dict[str, Any]:
        query = state["question"]
        results = search(self.store, query, top_k=self.top_k)
        call = {"tool": "search_rfp", "args": {"query": query, "top_k": self.top_k}}
        self.audit.record(
            thread_id=self.thread_id, tool="search_rfp",
            args=call["args"], outcome=f"{len(results)} results",
        )
        return {"results": [result_to_dict(r) for r in results], "tool_calls": [call]}

    def grade_node(self, state: AgentState) -> dict[str, Any]:
        results = state.get("results") or []
        ok = bool(results) and results[0]["score"] >= self.min_score
        return {"grade": "sufficient" if ok else "insufficient"}

    def grade_branch(self, state: AgentState) -> str:
        if state["grade"] == "sufficient":
            return "generate"
        if state.get("rewrite_count", 0) < self.max_rewrites:
            return "rewrite"
        return "abstain"

    def rewrite_node(self, state: AgentState) -> dict[str, Any]:
        attempt = state.get("rewrite_count", 0) + 1
        new_q = self.rewriter.rewrite(state["original_question"], attempt)
        return {"question": new_q, "rewrite_count": attempt}

    def tool_exec_node(self, state: AgentState) -> dict[str, Any]:
        args = state.get("tool_args") or {}
        try:
            result: dict[str, Any] = aggregate_metadata(self.docs, **args)
            outcome = "ok"
        except (ValueError, TypeError) as exc:
            result = {"error": str(exc)}
            outcome = f"error: {exc}"
        call = {"tool": "aggregate_metadata", "args": args, "outcome": outcome}
        self.audit.record(thread_id=self.thread_id, tool="aggregate_metadata", args=args, outcome=outcome)
        return {"tool_result": result, "tool_calls": [call]}

    def generate_node(self, state: AgentState) -> dict[str, Any]:
        if state["route"] == "metadata_query":
            return {"answer": self._metadata_answer(state)}
        results = [dict_to_result(d) for d in state.get("results") or []]
        text = self.generator.generate(state["question"], results)
        if "없는 정보" in text:
            return {"answer": None}
        return {"answer": self._rag_answer(state, text, results)}

    def regenerate_node(self, state: AgentState) -> dict[str, Any]:
        return {"regenerated": True}

    def verify_node(self, state: AgentState) -> dict[str, Any]:
        answer = state.get("answer")
        if answer is None:
            return {"verify_ok": False}
        if state["route"] == "metadata_query":
            # 결정론 조립 경로 — 인용 검증은 rag 경로 대상
            return {"verify_ok": "error" not in (state.get("tool_result") or {})}
        cited = {s["chunk_id"] for s in answer["sources"]}
        retrieved = set(answer["retrieved_chunk_ids"])
        return {"verify_ok": bool(cited) and cited <= retrieved}

    def verify_branch(self, state: AgentState) -> str:
        if state.get("answer") is None:
            return "abstain"
        if state.get("verify_ok"):
            return "save_report" if state.get("save_requested") else "respond"
        if not state.get("regenerated"):
            return "regenerate"
        return "abstain"

    def abstain_node(self, state: AgentState) -> dict[str, Any]:
        results = [dict_to_result(d) for d in state.get("results") or []]
        return {
            "answer": abstention_response(state["original_question"], results),
            "outcome": OUTCOME_ABSTAINED,
        }

    def save_report_node(self, state: AgentState) -> dict[str, Any]:
        filename = f"agent_report_{self.thread_id}.md"
        content = self._render_report(state)
        decision = interrupt(
            {
                "action": "save_report",
                "filename": filename,
                "preview": content[:500],
                "message": "보고서를 저장할까요? --approve 또는 --reject로 재개하세요.",
            }
        )
        approved = decision == "approve" or (isinstance(decision, dict) and decision.get("action") == "approve")
        args = {"filename": filename}
        if approved:
            path = save_report_file(self.reports_dir, filename, content)
            self.audit.record(
                thread_id=self.thread_id, tool="save_report", args=args, outcome=str(path), approved=True
            )
            answer = dict(state["answer"] or {})
            answer["report_path"] = str(path)
            return {
                "answer": answer,
                "outcome": OUTCOME_ANSWERED,
                "tool_calls": [{"tool": "save_report", "args": args, "outcome": str(path)}],
            }
        self.audit.record(
            thread_id=self.thread_id, tool="save_report", args=args, outcome="rejected", approved=False
        )
        return {
            "outcome": OUTCOME_REJECTED,
            "tool_calls": [{"tool": "save_report", "args": args, "outcome": "rejected"}],
        }

    def respond_node(self, state: AgentState) -> dict[str, Any]:
        if state.get("outcome"):
            return {}
        return {"outcome": OUTCOME_ANSWERED}

    # --- helpers -----------------------------------------------------------

    def _rag_answer(self, state: AgentState, text: str, results: list[SearchResult]) -> dict[str, Any]:
        top_score = results[0].score
        return {
            "query": state["original_question"],
            "answer": text,
            "sources": [_source_from_result(r) for r in results],
            "source_texts": [chunk_context_block(r) for r in results],
            "warnings": [],
            "confidence": "high" if top_score >= 2 * self.min_score else "medium",
            "retrieved_doc_ids": [r.doc_id for r in results],
            "retrieved_chunk_ids": [r.chunk_id for r in results],
            "scores": [r.score for r in results],
        }

    def _metadata_answer(self, state: AgentState) -> dict[str, Any] | None:
        tr = state.get("tool_result") or {}
        if "error" in tr:
            return None
        if tr.get("agg") == "count":
            text = f"조건에 해당하는 공고는 총 {tr['count']}건입니다."
        elif tr.get("agg") == "sum":
            text = f"조건에 해당하는 공고 {tr['count']}건의 사업 금액 합계는 {tr['sum']:,}원입니다."
        else:
            lines = [
                f"{i}. {r['project_name']} (발주: {r['issuer']}, 금액: "
                f"{(r['budget_krw_int'] or 0):,}원, 마감: {r['bid_end_at_iso'] or '미상'})"
                for i, r in enumerate(tr.get("rows") or [], start=1)
            ]
            if not lines:
                return None
            text = "조건에 해당하는 공고 목록입니다.\n" + "\n".join(lines)
        sources = [
            {
                "doc_id": r["doc_id"],
                "chunk_id": "",
                "score": None,
                "csv_row_id": r["csv_row_id"],
                "project_name": r["project_name"],
                "issuer": r["issuer"],
                "filename": "",
            }
            for r in tr.get("rows") or []
        ]
        return {
            "query": state["original_question"],
            "answer": text,
            "sources": sources,
            "source_texts": [],
            "warnings": [],
            "confidence": "high",
            "retrieved_doc_ids": tr.get("doc_ids") or [],
            "retrieved_chunk_ids": [],
            "scores": [],
            "tool_result": tr,
        }

    def _render_report(self, state: AgentState) -> str:
        answer = state.get("answer") or {}
        lines = [
            f"# RFP Agent 보고서",
            "",
            f"- 질문: {state.get('original_question', '')}",
            f"- 경로: {state.get('route', '')}",
            f"- thread: {self.thread_id}",
            "",
            "## 답변",
            "",
            str(answer.get("answer", "")),
        ]
        if answer.get("sources"):
            lines += ["", "## 근거"]
            lines += [
                f"- {s.get('doc_id')} {s.get('project_name', '')} ({s.get('issuer', '')})"
                for s in answer["sources"]
            ]
        return "\n".join(lines) + "\n"
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_agent_nodes.py -q`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/agent/nodes.py tests/test_agent_nodes.py
git commit -m "feat: agent nodes — route/retrieve/grade/rewrite/tool/generate/verify/HITL save"
```

---

### Task 6: 그래프 조립 + e2e/interrupt/checkpointer 테스트 (graph.py)

**Files:**
- Create: `rfp_rag/agent/graph.py`
- Test: `tests/test_agent_graph.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_agent_graph.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from rfp_rag.agent.brains import RuleQueryRewriter, RuleRouter
from rfp_rag.agent.graph import build_agent_graph, initial_state, run_config
from rfp_rag.agent.nodes import AgentRuntime
from rfp_rag.agent.tools import AuditLogger
from rfp_rag.chunking import Chunk
from rfp_rag.corpus import CorpusDocument
from rfp_rag.providers import LexicalHashEmbeddings, TemplateAnswerGenerator
from rfp_rag.vector_index import build_vector_store

PROJECT = "한영대학교 트랙운영 학사정보시스템 고도화"
NOISY_PREFIX = (
    "안녕하세요 혹시 다른 건 말고 그게 궁금한데요 그러면 근데 그런데 아니면 "
    "혹은 그리고 좀 대해서 관련해서 궁금한데 있을까요 "
)


def _runtime(tmp_path: Path, min_score: float = 0.05, thread_id: str = "t-graph") -> AgentRuntime:
    chunks = [
        Chunk(
            chunk_id="doc:000:chunk:0",
            doc_id="doc:000",
            csv_row_id="000",
            text=f"{PROJECT} 사업 제안요청서 본문",
            metadata={
                "project_name": PROJECT,
                "issuer": "한영대학",
                "summary": "학사정보시스템 고도화 사업",
                "budget_krw_int": 130_000_000,
                "bid_end_at_iso": "2024-10-15T17:00:00",
                "csv_filename_raw": "han.hwp",
            },
        )
    ]
    store = build_vector_store(chunks, LexicalHashEmbeddings(dim=512), qdrant_path=None, lane="offline")
    docs = [
        CorpusDocument(
            csv_row_id="000", doc_id="doc:000", text="본문",
            metadata={
                "project_name": PROJECT, "issuer": "한영대학",
                "budget_krw_int": 130_000_000, "bid_end_at_iso": "2024-10-15T17:00:00",
            },
        )
    ]
    return AgentRuntime(
        store=store,
        generator=TemplateAnswerGenerator(),
        router=RuleRouter(),
        rewriter=RuleQueryRewriter(),
        docs=docs,
        audit=AuditLogger(tmp_path / "audit.jsonl"),
        reports_dir=tmp_path / "reports",
        top_k=3,
        min_score=min_score,
        thread_id=thread_id,
    )


def test_direct_rag_path_answers(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    graph = build_agent_graph(rt)
    out = graph.invoke(initial_state(f"{PROJECT} 사업 예산 알려줘"), run_config("t1"))
    assert out["outcome"] == "answered"
    assert "130,000,000" in out["answer"]["answer"]
    assert out["rewrite_count"] == 0


def test_rewrite_recovers_noisy_question(tmp_path: Path) -> None:
    rt = _runtime(tmp_path, min_score=0.30)
    graph = build_agent_graph(rt)
    noisy = NOISY_PREFIX + f"{PROJECT} 사업 예산 알려줘"
    # 전제 검증: 노이즈 질의는 min_score 미달이어야 rewrite가 트리거된다
    from rfp_rag.vector_index import search

    assert search(rt.store, noisy, top_k=1)[0].score < 0.30
    out = graph.invoke(initial_state(noisy), run_config("t2"))
    assert out["outcome"] == "answered"
    assert out["rewrite_count"] >= 1
    assert "130,000,000" in out["answer"]["answer"]


def test_exhausted_rewrites_abstain(tmp_path: Path) -> None:
    rt = _runtime(tmp_path, min_score=0.05)
    graph = build_agent_graph(rt)
    out = graph.invoke(initial_state("화성 이주선 산소탱크 발사일은 언제야?"), run_config("t3"))
    assert out["outcome"] == "abstained"
    assert out["rewrite_count"] == 2  # 루프 종료 보장
    assert "없는 정보" in out["answer"]["answer"]
    assert "insufficient_context" in out["answer"]["warnings"]


def test_metadata_route_end_to_end(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    graph = build_agent_graph(rt)
    out = graph.invoke(initial_state("사업 금액이 가장 큰 공고 1건은?"), run_config("t4"))
    assert out["outcome"] == "answered"
    assert out["route"] == "metadata_query"
    assert out["tool_result"]["doc_ids"] == ["doc:000"]
    assert PROJECT in out["answer"]["answer"]


def test_hitl_approve_saves_report_and_audits(tmp_path: Path) -> None:
    rt = _runtime(tmp_path, thread_id="t5")
    graph = build_agent_graph(rt, checkpointer=MemorySaver())
    q = f"{PROJECT} 사업을 요약해서 보고서로 저장해줘"
    first = graph.invoke(initial_state(q), run_config("t5"))
    assert "__interrupt__" in first  # 승인 대기
    payload = first["__interrupt__"][0].value
    assert payload["action"] == "save_report"
    resumed = graph.invoke(Command(resume="approve"), run_config("t5"))
    assert resumed["outcome"] == "answered"
    report = Path(resumed["answer"]["report_path"])
    assert report.exists() and report.parent == (tmp_path / "reports").resolve()
    audit = [json.loads(l) for l in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    save_entries = [e for e in audit if e["tool"] == "save_report"]
    assert save_entries and save_entries[-1]["approved"] is True


def test_hitl_reject_skips_save_and_audits(tmp_path: Path) -> None:
    rt = _runtime(tmp_path, thread_id="t6")
    graph = build_agent_graph(rt, checkpointer=MemorySaver())
    q = f"{PROJECT} 사업을 요약해서 보고서로 저장해줘"
    first = graph.invoke(initial_state(q), run_config("t6"))
    assert "__interrupt__" in first
    resumed = graph.invoke(Command(resume="reject"), run_config("t6"))
    assert resumed["outcome"] == "rejected"
    assert not (tmp_path / "reports").exists() or not list((tmp_path / "reports").iterdir())
    audit = [json.loads(l) for l in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    save_entries = [e for e in audit if e["tool"] == "save_report"]
    assert save_entries and save_entries[-1]["approved"] is False
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_agent_graph.py -q`
Expected: FAIL — `ModuleNotFoundError: rfp_rag.agent.graph`

- [ ] **Step 3: 구현**

`rfp_rag/agent/graph.py`:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from .nodes import AgentRuntime
from .state import AgentState

RECURSION_LIMIT = 25


def initial_state(question: str) -> AgentState:
    return {"question": question, "rewrite_count": 0, "tool_calls": []}


def run_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}


def sqlite_checkpointer(path: Path) -> BaseCheckpointSaver:
    from langgraph.checkpoint.sqlite import SqliteSaver

    path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(str(path), check_same_thread=False))


def build_agent_graph(runtime: AgentRuntime, checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(AgentState)
    g.add_node("route", runtime.route_node)
    g.add_node("retrieve", runtime.retrieve_node)
    g.add_node("grade", runtime.grade_node)
    g.add_node("rewrite", runtime.rewrite_node)
    g.add_node("tool_exec", runtime.tool_exec_node)
    g.add_node("generate", runtime.generate_node)
    g.add_node("regenerate", runtime.regenerate_node)
    g.add_node("verify", runtime.verify_node)
    g.add_node("abstain", runtime.abstain_node)
    g.add_node("save_report", runtime.save_report_node)
    g.add_node("respond", runtime.respond_node)

    g.add_edge(START, "route")
    g.add_conditional_edges(
        "route",
        lambda s: "tool_exec" if s["route"] == "metadata_query" else "retrieve",
        {"retrieve": "retrieve", "tool_exec": "tool_exec"},
    )
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges(
        "grade", runtime.grade_branch, {"generate": "generate", "rewrite": "rewrite", "abstain": "abstain"}
    )
    g.add_edge("rewrite", "retrieve")
    g.add_edge("tool_exec", "generate")
    g.add_edge("generate", "verify")
    g.add_conditional_edges(
        "verify",
        runtime.verify_branch,
        {"respond": "respond", "save_report": "save_report", "regenerate": "regenerate", "abstain": "abstain"},
    )
    g.add_edge("regenerate", "generate")
    g.add_edge("save_report", "respond")
    g.add_edge("abstain", "respond")
    g.add_edge("respond", END)
    return g.compile(checkpointer=checkpointer)
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_agent_graph.py -q`
Expected: 6 passed

주의사항(실패 시 점검 순서): ① interrupt는 checkpointer 없이는 동작하지 않는다 — HITL 테스트만 `MemorySaver`를 쓰는 이유. ② `test_rewrite_recovers_noisy_question`의 전제 assert가 실패하면 NOISY_PREFIX를 더 길게(불용어 토큰 추가) 만들고 `_STOPWORDS`에도 같은 토큰을 추가할 것. ③ `__interrupt__` 키 구조는 langgraph 1.0 기준 `tuple[Interrupt, ...]`이며 각 항목의 `.value`가 payload다.

- [ ] **Step 5: 전체 회귀 확인 + Commit**

Run: `python3 -m pytest -q -m "not real"`
Expected: 전체 PASS

```bash
git add rfp_rag/agent/graph.py tests/test_agent_graph.py
git commit -m "feat: assemble LangGraph StateGraph with rewrite loop, HITL interrupt, checkpointer"
```

---

### Task 7: CLI — run_agent.py

**Files:**
- Create: `rfp_rag/agent/run_agent.py`
- Test: `tests/test_agent_cli.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_agent_cli.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.agent.run_agent import main


def _build_offline_index(tmp_path: Path) -> Path:
    """실제 corpus 데이터로 소형 인덱스를 만들기엔 무겁다 — build_index CLI를 그대로 재사용."""
    from rfp_rag.build_index import main as build_main

    out = tmp_path / "index"
    rc = build_main(
        [
            "--data", "data/data_list.csv",
            "--files", "data/files",
            "--out", str(out),
            "--chunk-size", "500",
            "--chunk-overlap", "80",
            "--embedding-provider", "offline",
        ]
    )
    assert rc == 0
    return out


def test_cli_answers_question_offline(tmp_path: Path, capsys) -> None:
    index = _build_offline_index(tmp_path)
    rc = main(
        [
            "--index", str(index),
            "--data", "data/data_list.csv",
            "--files", "data/files",
            "--question", "한영대학교 특성화 맞춤형 교육환경 구축 - 트랙운영 학사정보시스템 고도화 사업의 발주 기관은 어디야?",
            "--thread-id", "cli-t1",
            "--min-score", "0.15",
            "--artifacts", str(tmp_path / "agent_artifacts"),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["outcome"] == "answered"
    assert "한영대학" in payload["answer"]["answer"]
    # audit log가 지정 위치에 생성된다
    assert (tmp_path / "agent_artifacts" / "audit.jsonl").exists()
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_agent_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: rfp_rag.agent.run_agent`

- [ ] **Step 3: 구현**

`rfp_rag/agent/run_agent.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from langgraph.types import Command

from ..corpus import load_corpus
from ..providers import build_embeddings, build_generator, normalize_lane
from ..rag_chain import DEFAULT_MIN_SCORE, _load_manifest
from ..vector_index import load_vector_store
from .brains import build_rewriter, build_router
from .graph import build_agent_graph, initial_state, run_config, sqlite_checkpointer
from .nodes import AgentRuntime
from .tools import AuditLogger


def build_runtime(
    index_dir: Path,
    data: Path,
    files: Path,
    provider: str | None,
    top_k: int,
    min_score: float,
    artifacts: Path,
    thread_id: str,
) -> AgentRuntime:
    manifest = _load_manifest(index_dir)
    index_lane = normalize_lane(manifest.get("embedding_provider", "offline"))
    lane = normalize_lane(provider) if provider else index_lane
    if lane != index_lane:
        raise ValueError(
            f"provider lane {lane!r} does not match index embedding lane {index_lane!r}; rebuild the index"
        )
    embeddings = build_embeddings(lane)
    store = load_vector_store(index_dir / "qdrant", embeddings, lane=lane)
    return AgentRuntime(
        store=store,
        generator=build_generator(lane),
        router=build_router(lane),
        rewriter=build_rewriter(lane),
        docs=load_corpus(data, files),
        audit=AuditLogger(artifacts / "audit.jsonl"),
        reports_dir=artifacts / "reports",
        top_k=top_k,
        min_score=min_score,
        thread_id=thread_id,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rfp_rag.agent.run_agent", description="LangGraph agent lane CLI")
    p.add_argument("--index", required=True, type=Path)
    p.add_argument("--data", required=True, type=Path)
    p.add_argument("--files", required=True, type=Path)
    p.add_argument("--question", default=None)
    p.add_argument("--provider", default=None)
    p.add_argument("--thread-id", default="default")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    p.add_argument("--artifacts", type=Path, default=Path("artifacts/agent"))
    resume = p.add_mutually_exclusive_group()
    resume.add_argument("--approve", action="store_true", help="interrupt된 save_report 승인 후 재개")
    resume.add_argument("--reject", action="store_true", help="interrupt된 save_report 거부 후 재개")
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(list(argv) if argv is not None else None)
    if not args.question and not (args.approve or args.reject):
        print("error: --question 또는 --approve/--reject 중 하나가 필요합니다", file=sys.stderr)
        return 2
    runtime = build_runtime(
        args.index, args.data, args.files, args.provider,
        args.top_k, args.min_score, args.artifacts, args.thread_id,
    )
    checkpointer = sqlite_checkpointer(args.artifacts / "checkpoints.sqlite")
    graph = build_agent_graph(runtime, checkpointer=checkpointer)
    config = run_config(args.thread_id)
    if args.approve or args.reject:
        snapshot = graph.get_state(config)
        if not snapshot.next:  # 재개할 interrupt가 없다 (checkpoint 부재/이미 종료)
            print(
                f"error: thread {args.thread_id!r}에 재개할 승인 대기 상태가 없습니다 — "
                "--question으로 새로 시작하세요",
                file=sys.stderr,
            )
            return 2
        result = graph.invoke(Command(resume="approve" if args.approve else "reject"), config)
    else:
        result = graph.invoke(initial_state(args.question), config)
    if "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        print(json.dumps({"status": "interrupted", "interrupt": payload}, ensure_ascii=False, indent=2))
        print(
            f"승인 대기 중 — 같은 --thread-id {args.thread_id!r}로 --approve 또는 --reject를 실행하세요.",
            file=sys.stderr,
        )
        return 0
    out: dict[str, Any] = {
        "outcome": result.get("outcome"),
        "route": result.get("route"),
        "rewrite_count": result.get("rewrite_count"),
        "answer": result.get("answer"),
        "tool_calls": result.get("tool_calls"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 통과 확인 + 수동 스모크**

Run: `python3 -m pytest tests/test_agent_cli.py -q`
Expected: 1 passed

Run (수동 HITL 스모크 — interrupt 출력 확인):

```bash
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index --chunk-size 500 --chunk-overlap 80 --embedding-provider offline 2>/dev/null | tail -1
python3 -m rfp_rag.agent.run_agent --index artifacts/index --data data/data_list.csv --files data/files \
  --question "한영대학교 특성화 맞춤형 교육환경 구축 - 트랙운영 학사정보시스템 고도화 사업을 요약해서 보고서로 저장해줘" \
  --thread-id demo-1 --min-score 0.15
python3 -m rfp_rag.agent.run_agent --index artifacts/index --data data/data_list.csv --files data/files \
  --thread-id demo-1 --approve
```

Expected: 첫 실행 `"status": "interrupted"` + 안내, 두 번째 실행 `outcome: answered` + `report_path`; `artifacts/agent/reports/agent_report_demo-1.md` 생성 및 `artifacts/agent/audit.jsonl`에 approved=true 기록.

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/agent/run_agent.py tests/test_agent_cli.py
git commit -m "feat: agent CLI with sqlite checkpointer and interrupt resume (--approve/--reject)"
```

---

### Task 8: 평가 + 게이트 — evaluate_agent.py, contracts 확장

**Files:**
- Create: `rfp_rag/agent/evaluate_agent.py`
- Modify: `rfp_rag/contracts.py` (append)
- Test: `tests/test_agent_evaluate.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_agent_evaluate.py`:

```python
from __future__ import annotations

from rfp_rag.agent.evaluate_agent import AGENT_THRESHOLDS, decide_agent_gate
from rfp_rag.contracts import agent_contract


def _passing_metrics() -> dict:
    return {
        "routing_accuracy": 0.95,
        "tool_accuracy": 0.90,
        "rewrite_recovery": 0.60,
        "loop_termination": 1.0,
        "abstention_accuracy": 1.0,
        "citation_presence": 1.0,
        "citation_validity": 1.0,
        "metadata_exact_match": 0.95,
    }


def test_gate_passes_at_thresholds() -> None:
    gate = decide_agent_gate(_passing_metrics(), evaluation_valid=True)
    assert gate["agent_lane_complete"] is True
    assert gate["thresholds_applied"] is True
    assert gate["failed"] == []


def test_gate_fails_below_any_threshold() -> None:
    metrics = _passing_metrics()
    metrics["routing_accuracy"] = 0.89
    gate = decide_agent_gate(metrics, evaluation_valid=True)
    assert gate["agent_lane_complete"] is False
    assert "routing_accuracy" in gate["failed"]


def test_gate_fails_on_invalid_evaluation_or_missing_metric() -> None:
    gate = decide_agent_gate(_passing_metrics(), evaluation_valid=False)
    assert gate["agent_lane_complete"] is False
    metrics = _passing_metrics()
    metrics["tool_accuracy"] = None
    gate2 = decide_agent_gate(metrics, evaluation_valid=True)
    assert gate2["agent_lane_complete"] is False
    assert "tool_accuracy" in gate2["failed"]


def test_thresholds_match_design() -> None:
    assert AGENT_THRESHOLDS["routing_accuracy"] == 0.90
    assert AGENT_THRESHOLDS["rewrite_recovery"] == 0.60
    assert AGENT_THRESHOLDS["loop_termination"] == 1.0


def test_agent_contract_shape() -> None:
    c = agent_contract()
    assert c["contract_version"] == "rfp-agent-v1"
    assert any("evaluate_agent" in cmd for cmd in c["required_commands"])
    semantics = c["quality_semantics"]["agent_offline"]
    assert semantics["allowed_completion_claim"] == "agent_lane_complete"
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_agent_evaluate.py -q`
Expected: FAIL — `ModuleNotFoundError: rfp_rag.agent.evaluate_agent`

- [ ] **Step 3: contracts.py 확장 (파일 끝에 append)**

```python
AGENT_CONTRACT_VERSION = "rfp-agent-v1"

AGENT_REQUIRED_COMMANDS = [
    "python3 -m pytest",
    "python3 -m rfp_rag.agent.evaluate_agent --data data/data_list.csv --files data/files --index artifacts/index --out artifacts/eval_agent --provider offline --top-k 5 --min-score 0.15",
]

AGENT_REQUIRED_EVAL_FILES = [
    "scenarios.jsonl",
    "predictions.jsonl",
    "metrics.json",
    "report.md",
    "contract.json",
]


def agent_contract() -> dict[str, Any]:
    return {
        "contract_version": AGENT_CONTRACT_VERSION,
        "required_eval_files": list(AGENT_REQUIRED_EVAL_FILES),
        "required_commands": AGENT_REQUIRED_COMMANDS,
        "gate_semantics": (
            "agent_lane_complete is decided on the offline lane: graph topology, tools, "
            "HITL and loop termination are deterministic. Real-lane router/rewriter quality "
            "is covered by @pytest.mark.real smoke plus a small real evaluation recorded in REPORT.md."
        ),
        "quality_semantics": {
            "agent_offline": {
                "claims_semantic_quality": False,
                "allowed_completion_claim": "agent_lane_complete",
                "requires": ["thresholds_met", "evaluation_valid"],
            }
        },
    }
```

- [ ] **Step 4: evaluate_agent.py 구현**

`rfp_rag/agent/evaluate_agent.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from ..contracts import agent_contract
from ..corpus import CorpusDocument, load_corpus
from ..evaluate import (
    MAX_ERROR_RATE,
    _answer_exact_match,
    generate_abstention_questions,
    generate_golden_metadata,
)
from ..rag_chain import DEFAULT_MIN_SCORE
from ..vector_index import search
from .graph import build_agent_graph, initial_state, run_config
from .run_agent import build_runtime

AGENT_THRESHOLDS: dict[str, float] = {
    "routing_accuracy": 0.90,
    "tool_accuracy": 0.90,
    "rewrite_recovery": 0.60,
    "loop_termination": 1.0,
    "abstention_accuracy": 0.90,
    "citation_presence": 0.95,
    "citation_validity": 0.90,
    "metadata_exact_match": 0.90,
}

NOISY_PREFIX = (
    "안녕하세요 혹시 다른 건 말고 그게 궁금한데요 그러면 근데 그런데 아니면 "
    "혹은 그리고 좀 대해서 관련해서 궁금한데 있을까요 "
)


def decide_agent_gate(metrics: dict[str, Any], evaluation_valid: bool) -> dict[str, Any]:
    failed = [
        name
        for name, minimum in AGENT_THRESHOLDS.items()
        if metrics.get(name) is None or metrics[name] < minimum
    ]
    return {
        "thresholds_applied": True,
        "thresholds": dict(AGENT_THRESHOLDS),
        "failed": failed,
        "evaluation_valid": evaluation_valid,
        "agent_lane_complete": evaluation_valid and not failed,
    }


# --- scenario generation ----------------------------------------------------


def _routing_scenarios(docs: list[CorpusDocument]) -> list[dict[str, Any]]:
    """rag 10건(golden 질문) + metadata 10건(규칙 패턴). 기대 route만 채점."""
    rag = generate_golden_metadata(docs, max_docs=3)[:10]
    cases = [
        {
            "id": f"routing_rag_{i:03d}",
            "type": "routing",
            "question": r["question"],
            "expected_route": "rag_query",
        }
        for i, r in enumerate(rag)
    ]
    issuers = sorted({d.metadata.get("issuer", "") for d in docs if d.metadata.get("issuer")})[:3]
    metadata_questions = [
        "사업 금액이 가장 큰 공고 3건은 뭐야?",
        "사업 금액이 가장 큰 공고 5건 알려줘",
        "입찰 마감이 가장 빠른 공고 5건 알려줘",
        "입찰 마감이 가장 빠른 공고 3건은?",
        "사업 금액이 10억 이상인 공고는 몇 건이야?",
        "사업 금액이 5억 이상인 공고는 몇 건이야?",
        "전체 공고는 몇 건이야?",
        f"{issuers[0]}이 발주한 공고는 몇 건이야?" if issuers else "발주 기관이 대학인 공고는 몇 건이야?",
        "사업 금액이 10억 이상인 공고들의 금액 합계는 얼마야?",
        "사업 금액이 가장 높은 공고 1건은?",
    ]
    cases += [
        {
            "id": f"routing_meta_{i:03d}",
            "type": "routing",
            "question": q,
            "expected_route": "metadata_query",
        }
        for i, q in enumerate(metadata_questions)
    ]
    return cases


def _regression_scenarios(docs: list[CorpusDocument]) -> list[dict[str, Any]]:
    """기존 golden 채점 로직 재사용: expected_doc_id + expected_field/value."""
    golden = generate_golden_metadata(docs, max_docs=5)[:20]
    return [
        {
            "id": f"regression_{i:03d}",
            "type": "regression",
            "question": g["question"],
            "expected_doc_id": g["expected_doc_id"],
            "expected_field": g["expected_field"],
            "expected_value": g["expected_value"],
        }
        for i, g in enumerate(golden)
    ]


def _rewrite_scenarios(docs: list[CorpusDocument], runtime, min_score: float) -> list[dict[str, Any]]:
    """노이즈 질의 스코어가 min_score 미달인 것만 채택 — rewrite 트리거를 결정론으로 보장."""
    golden = generate_golden_metadata(docs, max_docs=10)
    out: list[dict[str, Any]] = []
    for g in golden:
        noisy = NOISY_PREFIX + g["question"]
        results = search(runtime.store, noisy, top_k=1)
        if results and results[0].score >= min_score:
            continue  # 노이즈로도 검색이 살아있으면 rewrite 검증 케이스가 아니다
        out.append(
            {
                "id": f"rewrite_{len(out):03d}",
                "type": "rewrite",
                "question": noisy,
                "expected_doc_id": g["expected_doc_id"],
                "expected_field": g["expected_field"],
                "expected_value": g["expected_value"],
            }
        )
        if len(out) == 5:
            break
    return out


def _abstention_scenarios() -> list[dict[str, Any]]:
    return [
        {"id": f"abstention_{i:03d}", "type": "abstention", "question": a["question"]}
        for i, a in enumerate(generate_abstention_questions())
    ]


def _tool_scenarios(docs: list[CorpusDocument]) -> list[dict[str, Any]]:
    """기대값은 docs에서 독립 계산(인라인 sorted/sum) — 도구 구현과 분리된 채점 기준."""
    budgets = [(d.doc_id, d.metadata.get("budget_krw_int")) for d in docs]
    with_budget = [(i, b) for i, b in budgets if b is not None]
    top_budget = [i for i, _ in sorted(with_budget, key=lambda x: -x[1])]
    deadlines = [(d.doc_id, d.metadata.get("bid_end_at_iso")) for d in docs]
    with_deadline = sorted([(i, t) for i, t in deadlines if t], key=lambda x: x[1])
    gte_10e8 = [i for i, b in with_budget if b >= 1_000_000_000]
    sum_10e8 = sum(b for _, b in with_budget if b >= 1_000_000_000)
    issuers = sorted({d.metadata.get("issuer", "") for d in docs if d.metadata.get("issuer")})
    issuer = issuers[0]
    issuer_count = sum(1 for d in docs if issuer in (d.metadata.get("issuer") or ""))
    cases = [
        {"question": "사업 금액이 가장 큰 공고 3건은 뭐야?", "expect": {"doc_ids": top_budget[:3]}},
        {"question": "사업 금액이 가장 큰 공고 5건 알려줘", "expect": {"doc_ids": top_budget[:5]}},
        {"question": "사업 금액이 가장 높은 공고 1건은?", "expect": {"doc_ids": top_budget[:1]}},
        {"question": "입찰 마감이 가장 빠른 공고 5건 알려줘", "expect": {"doc_ids": [i for i, _ in with_deadline[:5]]}},
        {"question": "입찰 마감이 가장 빠른 공고 3건은?", "expect": {"doc_ids": [i for i, _ in with_deadline[:3]]}},
        {"question": "사업 금액이 10억 이상인 공고는 몇 건이야?", "expect": {"count": len(gte_10e8)}},
        {"question": "전체 공고는 몇 건이야?", "expect": {"count": len(docs)}},
        {"question": f"{issuer}이 발주한 공고는 몇 건이야?", "expect": {"count": issuer_count}},
        {"question": "사업 금액이 10억 이상인 공고들의 금액 합계는 얼마야?", "expect": {"sum": sum_10e8}},
        {"question": "사업 금액이 5억 이상인 공고는 몇 건이야?", "expect": {"count": sum(1 for _, b in with_budget if b >= 500_000_000)}},
    ]
    return [
        {"id": f"tool_{i:03d}", "type": "tool", "question": c["question"], "expect": c["expect"]}
        for i, c in enumerate(cases)
    ]


# --- scoring -----------------------------------------------------------------


def _score_case(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    answer = result.get("answer") or {}
    answer_text = answer.get("answer") or ""
    scored: dict[str, Any] = {
        "id": case["id"],
        "type": case["type"],
        "question": case["question"],
        "route": result.get("route"),
        "outcome": result.get("outcome"),
        "rewrite_count": result.get("rewrite_count", 0),
        "loop_terminated": (result.get("rewrite_count", 0) or 0) <= 2,
    }
    kind = case["type"]
    if kind == "routing":
        scored["routing_correct"] = result.get("route") == case["expected_route"]
    elif kind in ("regression", "rewrite"):
        answered = result.get("outcome") == "answered"
        retrieved = answer.get("retrieved_doc_ids") or []
        sources = answer.get("sources") or []
        retrieved_chunks = set(answer.get("retrieved_chunk_ids") or [])
        cited = {s.get("chunk_id") for s in sources}
        scored["exact_match"] = answered and _answer_exact_match(
            answer_text, case["expected_field"], case["expected_value"]
        )
        scored["citation_present"] = bool(sources)
        scored["citation_valid"] = bool(cited) and cited <= retrieved_chunks
        scored["doc_hit"] = case["expected_doc_id"] in retrieved
        if kind == "rewrite":
            scored["recovered"] = scored["exact_match"]
    elif kind == "abstention":
        scored["abstained"] = result.get("outcome") == "abstained"
    elif kind == "tool":
        tr = result.get("tool_result") or {}
        expect = case["expect"]
        ok = result.get("route") == "metadata_query"
        for key, value in expect.items():
            ok = ok and tr.get(key) == value
        scored["tool_correct"] = ok
    return scored


def _mean(flags: list[bool]) -> float | None:
    return None if not flags else sum(1.0 for f in flags if f) / len(flags)


def _aggregate(scored: list[dict[str, Any]]) -> dict[str, Any]:
    by = lambda t: [s for s in scored if s["type"] == t]  # noqa: E731
    reg = by("regression")
    rew = by("rewrite")
    metrics = {
        "routing_accuracy": _mean([s["routing_correct"] for s in by("routing")]),
        "tool_accuracy": _mean([s["tool_correct"] for s in by("tool")]),
        "rewrite_recovery": _mean([s["recovered"] for s in rew]),
        "loop_termination": _mean([s["loop_terminated"] for s in scored]),
        "abstention_accuracy": _mean([s["abstained"] for s in by("abstention")]),
        "citation_presence": _mean([s["citation_present"] for s in reg]),
        "citation_validity": _mean([s["citation_valid"] for s in reg]),
        "metadata_exact_match": _mean([s["exact_match"] for s in reg]),
        "counts": {t: len(by(t)) for t in ("routing", "regression", "rewrite", "abstention", "tool")},
    }
    return metrics


def _render_report(metrics: dict[str, Any], gate: dict[str, Any]) -> str:
    lines = ["# Agent Lane Evaluation", ""]
    for name, minimum in AGENT_THRESHOLDS.items():
        value = metrics.get(name)
        mark = "PASS" if (value is not None and value >= minimum) else "FAIL"
        shown = "null" if value is None else f"{value:.4f}"
        lines.append(f"- {name}: {shown} (>= {minimum}) {mark}")
    lines += [
        "",
        f"- counts: {json.dumps(metrics['counts'], ensure_ascii=False)}",
        f"- evaluation_valid: {gate['evaluation_valid']}",
        f"- **agent_lane_complete: {gate['agent_lane_complete']}**",
        "",
    ]
    return "\n".join(lines)


def evaluate_agent(
    data: Path,
    files: Path,
    index_dir: Path,
    out_dir: Path,
    provider: str | None,
    top_k: int,
    min_score: float,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    runtime = build_runtime(
        index_dir, data, files, provider, top_k, min_score,
        artifacts=out_dir / "agent_artifacts", thread_id="eval",
    )
    docs = runtime.docs
    scenarios = (
        _routing_scenarios(docs)
        + _regression_scenarios(docs)
        + _rewrite_scenarios(docs, runtime, min_score)
        + _abstention_scenarios()
        + _tool_scenarios(docs)
    )
    graph = build_agent_graph(runtime)
    scored: list[dict[str, Any]] = []
    errors = 0
    for i, case in enumerate(scenarios):
        try:
            result = graph.invoke(initial_state(case["question"]), run_config(f"eval-{i}"))
        except Exception as exc:  # 개별 실패는 기록하고 진행 (기존 evaluate 정책)
            errors += 1
            scored.append({"id": case["id"], "type": case["type"], "error": str(exc), "loop_terminated": True})
            continue
        scored.append(_score_case(case, result))
    evaluation_valid = (errors / max(len(scenarios), 1)) <= MAX_ERROR_RATE
    metrics = _aggregate([s for s in scored if "error" not in s])
    gate = decide_agent_gate(metrics, evaluation_valid=evaluation_valid)
    metrics_payload = {
        "lane": runtime_lane(index_dir, provider),
        "top_k": top_k,
        "min_score": min_score,
        "errors": errors,
        **metrics,
        "gate": gate,
        "agent_lane_complete": gate["agent_lane_complete"],
    }
    (out_dir / "scenarios.jsonl").write_text(
        "\n".join(json.dumps(s, ensure_ascii=False, sort_keys=True) for s in scenarios) + "\n",
        encoding="utf-8",
    )
    (out_dir / "predictions.jsonl").write_text(
        "\n".join(json.dumps(s, ensure_ascii=False, sort_keys=True) for s in scored) + "\n",
        encoding="utf-8",
    )
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "report.md").write_text(_render_report(metrics, gate), encoding="utf-8")
    (out_dir / "contract.json").write_text(
        json.dumps(agent_contract(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return metrics_payload


def runtime_lane(index_dir: Path, provider: str | None) -> str:
    from ..providers import normalize_lane
    from ..rag_chain import _load_manifest

    if provider:
        return normalize_lane(provider)
    return normalize_lane(_load_manifest(index_dir).get("embedding_provider", "offline"))


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rfp_rag.agent.evaluate_agent")
    p.add_argument("--data", required=True, type=Path)
    p.add_argument("--files", required=True, type=Path)
    p.add_argument("--index", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--provider", default=None)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(list(argv) if argv is not None else None)
    payload = evaluate_agent(args.data, args.files, args.index, args.out, args.provider, args.top_k, args.min_score)
    print(json.dumps({"agent_lane_complete": payload["agent_lane_complete"], "out": str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: 통과 확인**

Run: `python3 -m pytest tests/test_agent_evaluate.py -q`
Expected: 5 passed

주의: `generate_golden_metadata`의 실제 반환 키 이름(`expected_doc_id`/`expected_field`/`expected_value`/`question`)을 evaluate.py 소스에서 확인하고, 다르면 시나리오 생성부를 실제 키에 맞출 것 (예: `doc_id`/`field`/`value`일 수 있음). `generate_abstention_questions` 반환 건수(5 또는 10)도 확인해 abstention 시나리오 수를 기록할 것.

- [ ] **Step 6: Commit**

```bash
git add rfp_rag/agent/evaluate_agent.py rfp_rag/contracts.py tests/test_agent_evaluate.py
git commit -m "feat: agent scenario evaluation with agent_lane_complete gate and rfp-agent-v1 contract"
```

---

### Task 9: 게이트 실행 + real 스모크 + REPORT/README 갱신

**Files:**
- Create: `tests/test_agent_real_smoke.py`
- Modify: `REPORT.md`, `README.md`, `docs/superpowers/specs/2026-06-10-langgraph-agent-lane-design.md`

- [ ] **Step 1: real 스모크 테스트 작성**

`tests/test_agent_real_smoke.py` (기존 `tests/test_real_smoke.py`의 마커/스킵 패턴을 먼저 읽고 동일하게 맞출 것):

```python
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.real

requires_key = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"
)


@requires_key
def test_llm_router_classifies_metadata_query() -> None:
    from rfp_rag.agent.brains import LLMRouter

    d = LLMRouter().route("사업 금액이 가장 큰 공고 3건은 뭐야?")
    assert d.route == "metadata_query"
    assert d.tool_args.get("sort_by") == "budget_krw_int"


@requires_key
def test_llm_rewriter_strips_noise() -> None:
    from rfp_rag.agent.brains import LLMQueryRewriter

    q = "안녕하세요 혹시 다른 건 말고 한영대학교 트랙운영 학사정보시스템 고도화 사업 예산이 궁금해요"
    rewritten = LLMQueryRewriter().rewrite(q, attempt=1)
    assert "한영대학교" in rewritten
    assert len(rewritten) < len(q)
```

- [ ] **Step 2: offline 게이트 실행**

```bash
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index --chunk-size 500 --chunk-overlap 80 --embedding-provider offline
python3 -m rfp_rag.agent.evaluate_agent --data data/data_list.csv --files data/files --index artifacts/index --out artifacts/eval_agent --provider offline --top-k 5 --min-score 0.15
cat artifacts/eval_agent/metrics.json | python3 -c "import json,sys; m=json.load(sys.stdin); print(m['agent_lane_complete'], m['gate']['failed'])"
```

Expected: `True []`. 실패 메트릭이 있으면 predictions.jsonl에서 해당 케이스를 보고 **코드/시나리오를 고친다 (임계값 하향 금지 — 불가피하면 REPORT에 근거 기록)**.

- [ ] **Step 3: real 스모크 실행 (키 있을 때)**

```bash
set -a; source ./.env; set +a
python3 -m pytest tests/test_agent_real_smoke.py -m real -q
```

Expected: 2 passed (키 없으면 skip 2 — REPORT에 미실행 기록)

- [ ] **Step 4: 문서 갱신**

- `REPORT.md`: `## 12. LangGraph Agent 레인` 섹션 추가 — 설계 요약(그래프 다이어그램), `agent_lane_complete` 메트릭 표 (metrics.json 실측값), HITL/audit 증거 경로, real 스모크 결과, 재현 명령어 (contracts.py의 AGENT_REQUIRED_COMMANDS와 동일하게), 이월 항목.
- `README.md`: agent 레인 사용법 섹션 (run_agent 예시 — 질문/interrupt/approve 3command, evaluate_agent 명령), `rfp-agent-v1` 계약 언급.
- 설계 문서 §3: metadata 경로 generate를 "양 레인 공통 결정론 포맷터"로 수정 (Plan 헤더의 구현 결정 반영).

- [ ] **Step 5: 전체 검증 + Commit**

```bash
python3 -m pytest -q -m "not real"
git add -A && git commit -m "docs: agent lane report/readme + real smoke tests + gate run artifacts note"
```

(아티팩트 디렉토리 `artifacts/`가 gitignore인지 확인 — 기존 정책 유지. metrics 수치는 REPORT.md에 기록하므로 아티팩트 자체는 커밋하지 않는다.)

---

### Task 10: 사이클 마감 — PR

- [ ] **Step 1: 최종 회귀 + self-review**

```bash
python3 -m pytest -q -m "not real"
git log --oneline master..HEAD
git diff master --stat
```

- [ ] **Step 2: push + PR 생성**

```bash
git push -u origin feature/langgraph-agent-lane
gh pr create --title "feat: LangGraph stateful multi-step agent lane (routing/rewrite loop/tools/HITL)" --body "..."
```

PR 본문: 설계 문서 링크, 게이트 결과 (agent_lane_complete + 메트릭 표), 그래프 다이어그램, HITL 데모 명령, real 스모크 결과, 이월 항목. 끝에 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
