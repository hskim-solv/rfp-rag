from __future__ import annotations

from rfp_rag.agent.brains import (
    RuleQueryRewriter,
    RuleRouter,
    build_rewriter,
    build_router,
)


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
    assert {
        "field": "issuer",
        "op": "contains",
        "value": "한국전력공사",
    } in d.tool_args["filters"]


def test_rule_router_sum_query() -> None:
    d = RuleRouter().route("사업 금액이 10억 이상인 공고들의 금액 합계는 얼마야?")
    assert d.route == "metadata_query"
    assert d.tool_args["agg"] == "sum"
    assert d.tool_args["agg_field"] == "budget_krw_int"
    assert {
        "field": "budget_krw_int",
        "op": "gte",
        "value": 1_000_000_000,
    } in d.tool_args["filters"]


def test_rule_router_deadline_query() -> None:
    d = RuleRouter().route("입찰 마감이 가장 빠른 공고 5건 알려줘")
    assert d.route == "metadata_query"
    assert d.tool_args["sort_by"] == "bid_end_at_iso"
    assert d.tool_args["descending"] is False
    assert d.tool_args["top_n"] == 5


def test_rule_router_rag_default_and_save_flag() -> None:
    d = RuleRouter().route(
        "한영대학교 트랙운영 학사정보시스템 고도화 사업을 요약해서 보고서로 저장해줘"
    )
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
