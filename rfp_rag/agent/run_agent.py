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
from ..tracing import flush_tracing, traced_config
from ..vector_index import load_vector_store
from .brains import build_rewriter, build_router
from .graph import (
    build_agent_graph,
    close_checkpointer,
    initial_state,
    run_config,
    sqlite_checkpointer,
)
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
    p = argparse.ArgumentParser(
        prog="rfp_rag.agent.run_agent", description="LangGraph agent lane CLI"
    )
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
    resume.add_argument(
        "--approve", action="store_true", help="interrupt된 save_report 승인 후 재개"
    )
    resume.add_argument(
        "--reject", action="store_true", help="interrupt된 save_report 거부 후 재개"
    )
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(list(argv) if argv is not None else None)
    checkpointer = None
    if not args.question and not (args.approve or args.reject):
        print(
            "error: --question 또는 --approve/--reject 중 하나가 필요합니다",
            file=sys.stderr,
        )
        return 2
    try:
        runtime = build_runtime(
            args.index,
            args.data,
            args.files,
            args.provider,
            args.top_k,
            args.min_score,
            args.artifacts,
            args.thread_id,
        )
        checkpointer = sqlite_checkpointer(args.artifacts / "checkpoints.sqlite")
        graph = build_agent_graph(runtime, checkpointer=checkpointer)
        config = traced_config(run_config(args.thread_id))
        if args.approve or args.reject:
            snapshot = graph.get_state(config)
            if not snapshot.next:  # 재개할 interrupt가 없다 (checkpoint 부재/이미 종료)
                print(
                    f"error: thread {args.thread_id!r}에 재개할 승인 대기 상태가 없습니다 — "
                    "--question으로 새로 시작하세요",
                    file=sys.stderr,
                )
                return 2
            result = graph.invoke(
                Command(resume="approve" if args.approve else "reject"), config
            )
        else:
            result = graph.invoke(initial_state(args.question), config)
    finally:
        close_checkpointer(checkpointer)
        flush_tracing()  # 예외 경로 포함 — 단명 CLI에서 배치 전송 보장
    if "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        print(
            json.dumps(
                {"status": "interrupted", "interrupt": payload},
                ensure_ascii=False,
                indent=2,
            )
        )
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
