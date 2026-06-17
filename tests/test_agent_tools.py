from __future__ import annotations

import json
from pathlib import Path

import pytest

from rfp_rag.agent.tools import (
    AuditLogger,
    aggregate_metadata,
    report_filename,
    save_report_file,
)
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
    out = aggregate_metadata(
        _docs(), sort_by="budget_krw_int", descending=True, top_n=2
    )
    assert [r["doc_id"] for r in out["rows"]] == ["doc:002", "doc:001"]
    assert out["count"] == 3  # count는 필터 후 전체 건수 (top_n 무관)
    assert out["doc_ids"] == ["doc:002", "doc:001"]


def test_aggregate_sort_deadline_asc_puts_none_last() -> None:
    out = aggregate_metadata(
        _docs(), sort_by="bid_end_at_iso", descending=False, top_n=3
    )
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
        aggregate_metadata(
            _docs(), filters=[{"field": "csv_filename_raw", "op": "eq", "value": "x"}]
        )
    with pytest.raises(ValueError, match="unsupported filter"):
        aggregate_metadata(
            _docs(), filters=[{"field": "issuer", "op": "regex", "value": "x"}]
        )
    with pytest.raises(ValueError, match="unsupported sort_by"):
        aggregate_metadata(_docs(), sort_by="text")


def test_save_report_file_writes_inside_reports_dir(tmp_path: Path) -> None:
    target = save_report_file(
        tmp_path / "reports", "agent_report_t1.md", "# 보고서\n내용"
    )
    assert target.read_text(encoding="utf-8").startswith("# 보고서")
    assert target.parent == (tmp_path / "reports").resolve()


def test_save_report_file_rejects_path_escape_and_bad_ext(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid report filename"):
        save_report_file(tmp_path, "../escape.md", "x")
    with pytest.raises(ValueError, match="invalid report filename"):
        save_report_file(tmp_path, "sub/dir.md", "x")
    with pytest.raises(ValueError, match="invalid report filename"):
        save_report_file(tmp_path, "note.txt", "x")


def test_report_filename_safe_id_passthrough() -> None:
    assert report_filename("default") == "agent_report_default.md"


def test_report_filename_sanitized_result_is_saveable(tmp_path: Path) -> None:
    # trailing 단일 점은 '.md' 결합부에서 '..'를 만들고, 긴 id는 파일명 길이 한계를 넘긴다
    for thread_id in (
        "user/123",
        "a b@c",
        "..",
        "ns:sess/7",
        "run1.",
        "v1.",
        ".",
        "x" * 300,
        "가" * 120,
    ):
        name = report_filename(thread_id)
        target = save_report_file(tmp_path / "reports", name, "x")
        assert target.parent == (tmp_path / "reports").resolve()


def test_report_filename_distinct_ids_do_not_collide() -> None:
    # sanitize가 같은 문자열로 수렴해도 (user/123 vs user:123) 해시 접미로 구분된다
    names = {report_filename(t) for t in ("user/123", "user:123", "user_123")}
    assert len(names) == 3
    # trailing dot 제거가 기존 id와 충돌하지 않는다 (v1. vs v1)
    assert report_filename("v1.") != report_filename("v1")


def test_audit_logger_appends_jsonl(tmp_path: Path) -> None:
    audit = AuditLogger(tmp_path / "audit.jsonl")
    audit.record(
        thread_id="t1", tool="search_rfp", args={"query": "q"}, outcome="3 results"
    )
    audit.record(
        thread_id="t1",
        tool="save_report",
        args={"filename": "a.md"},
        outcome="rejected",
        approved=False,
    )
    lines = [
        json.loads(line)
        for line in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(lines) == 2
    assert lines[0]["tool"] == "search_rfp" and lines[0]["approved"] is None
    assert lines[1]["approved"] is False and lines[1]["thread_id"] == "t1"
    assert all("ts" in line for line in lines)
