from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from .index_store import SearchResult, load_index, retrieve

DEFAULT_MIN_SCORE = 0.25


def _source_from_result(result: SearchResult) -> dict[str, Any]:
    md = result.metadata
    return {
        "doc_id": result.doc_id,
        "chunk_id": result.chunk_id,
        "score": result.score,
        "csv_row_id": result.csv_row_id,
        "project_name": md.get("project_name", ""),
        "issuer": md.get("issuer", ""),
        "filename": md.get("csv_filename_raw", ""),
    }


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


def _context_answer(top: SearchResult) -> str:
    md = top.metadata
    project = md.get("project_name", "검색된 사업")
    issuer = md.get("issuer", "발주기관 미상")
    summary = (md.get("summary") or "").strip()
    if summary:
        return f"검색된 근거 기준으로 {project}는 {issuer}의 사업이며, 주요 내용은 다음과 같습니다. {summary}"
    snippet = " ".join((top.text or "").split())[:350]
    return f"검색된 근거 기준으로 {project}는 {issuer}의 사업입니다. 관련 본문: {snippet}"


def answer_query(index_dir: Path | str, query: str, top_k: int = 5, min_score: float = DEFAULT_MIN_SCORE) -> dict[str, Any]:
    index = load_index(index_dir)
    results = retrieve(index, query, top_k=top_k)
    retrieved_doc_ids = [r.doc_id for r in results]
    retrieved_chunk_ids = [r.chunk_id for r in results]
    scores = [r.score for r in results]
    if not results or results[0].score < min_score:
        return {
            "query": query,
            "answer": "검색된 제안요청서 근거만으로는 답할 수 없는 정보입니다. 없는 정보",
            "sources": [],
            "warnings": ["insufficient_context"],
            "confidence": "low",
            "retrieved_doc_ids": retrieved_doc_ids,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "scores": scores,
        }

    top = results[0]
    answer = _metadata_answer(query, top) or _context_answer(top)
    sources = [_source_from_result(result) for result in results]
    return {
        "query": query,
        "answer": answer,
        "sources": sources,
        "warnings": [],
        "confidence": "medium" if top.score < 0.12 else "high",
        "retrieved_doc_ids": retrieved_doc_ids,
        "retrieved_chunk_ids": retrieved_chunk_ids,
        "scores": scores,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Answer a Korean RFP question from a local index with citations.")
    parser.add_argument("--index", required=True, type=Path, help="Index directory")
    parser.add_argument("--query", required=True, help="Question to answer")
    parser.add_argument("--top-k", default=5, type=int)
    parser.add_argument("--min-score", default=DEFAULT_MIN_SCORE, type=float)
    parser.add_argument("--out", type=Path, help="Optional JSON output path")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    response = answer_query(args.index, args.query, top_k=args.top_k, min_score=args.min_score)
    payload = json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
