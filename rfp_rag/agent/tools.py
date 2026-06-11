from __future__ import annotations

import hashlib
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
        return {
            "agg": "sum",
            "agg_field": field,
            "sum": total,
            "count": count,
            "rows": [],
            "doc_ids": [],
        }

    if sort_by is not None:
        # None 값은 정렬 방향과 무관하게 항상 뒤로 보낸다.
        with_value = [d for d in selected if d.metadata.get(sort_by) is not None]
        without = [d for d in selected if d.metadata.get(sort_by) is None]
        with_value.sort(key=lambda d: d.metadata[sort_by], reverse=descending)
        selected = with_value + without
    rows = [
        {
            "doc_id": d.doc_id,
            "csv_row_id": d.csv_row_id,
            **{k: d.metadata.get(k) for k in ROW_FIELDS},
        }
        for d in selected[: max(int(top_n), 0)]
    ]
    return {
        "agg": "list",
        "count": count,
        "rows": rows,
        "doc_ids": [r["doc_id"] for r in rows],
    }


_FILENAME_RE = re.compile(r"^[0-9A-Za-z가-힣._-]+\.md$")
# 접두("agent_report_") + 해시 접미("-xxxxxxxx") + ".md"를 더해도 255바이트 안에 들어가는 예산
_MAX_SAFE_ID_BYTES = 100


def report_filename(thread_id: str) -> str:
    """thread_id 기반 보고서 파일명. CLI --thread-id는 무제약이라 sanitize 필수.

    안전한 id는 그대로 쓰고, 변형이 발생한 경우에만 해시 접미를 붙여
    서로 다른 id가 같은 파일명으로 수렴하는 충돌을 막는다.
    """
    safe = re.sub(r"[^0-9A-Za-z가-힣._-]", "_", thread_id)
    safe = re.sub(r"\.{2,}", "_", safe)  # '..' 잔존 시 save_report_file이 거부한다
    while len(safe.encode("utf-8")) > _MAX_SAFE_ID_BYTES:  # 파일명 255바이트 한계 대비
        safe = safe[:-1]
    safe = safe.rstrip(".")  # 단일 trailing dot도 '.md' 결합부에서 '..'가 된다
    if not safe:
        safe = "thread"
    if safe != thread_id:
        safe = f"{safe}-{hashlib.sha1(thread_id.encode('utf-8')).hexdigest()[:8]}"
    return f"agent_report_{safe}.md"


def save_report_file(reports_dir: Path, filename: str, content: str) -> Path:
    """reports_dir 하위에만 .md 저장. 경로 구분자/탈출 차단."""
    if not _FILENAME_RE.match(filename or "") or ".." in filename:
        raise ValueError(
            f"invalid report filename: {filename!r} (expected <name>.md, no path separators)"
        )
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
