from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from fastapi.testclient import TestClient

from rfp_rag.service import app as service_app


@contextmanager
def _pushd(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


@contextmanager
def _lightweight_answer(enabled: bool) -> Iterator[None]:
    if not enabled:
        yield
        return
    original = service_app.answer_query

    def fake_answer_query(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "answer": "service ops smoke response",
            "confidence": "low",
            "warnings": [],
            "sources": [],
            "retrieved_doc_ids": [],
            "retrieved_chunk_ids": [],
            "scores": [],
            "reranker": "none",
            "rerank_candidate_k": 5,
        }

    service_app.answer_query = fake_answer_query
    try:
        yield
    finally:
        service_app.answer_query = original


@contextmanager
def _lightweight_gates(enabled: bool) -> Iterator[None]:
    if not enabled:
        yield
        return
    original = service_app.collect_gate_status

    def fake_collect_gate_status(root: Path) -> dict[str, Any]:
        return {
            "overall_ok": False,
            "root": str(root),
            "mode": "service_ops_lightweight_smoke",
        }

    service_app.collect_gate_status = fake_collect_gate_status
    try:
        yield
    finally:
        service_app.collect_gate_status = original


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _pass_metric(ok: bool) -> float:
    return 1.0 if ok else 0.0


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _request_latency_ms(callable_request) -> tuple[Any, float]:
    started = time.perf_counter()
    response = callable_request()
    return response, (time.perf_counter() - started) * 1000


def evaluate_service_ops(
    *,
    root: Path = Path("."),
    out: Path | None = None,
    question: str = "테스트 사업을 근거와 함께 요약해줘",
    full_answer: bool = False,
    full_gates: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    out = out or root / "artifacts/service_ops/summary.json"
    latencies: list[float] = []
    failures: list[str] = []

    with (
        _pushd(root),
        _lightweight_answer(not full_answer),
        _lightweight_gates(not full_gates),
    ):
        client = TestClient(service_app.create_app(), raise_server_exceptions=False)

        healthz, latency = _request_latency_ms(lambda: client.get("/healthz"))
        latencies.append(latency)
        healthz_ok = healthz.status_code == 200 and healthz.json().get("ok") is True

        answer_payload = {
            "question": question,
            "index_dir": "artifacts/index",
            "provider": "offline",
        }
        answer, latency = _request_latency_ms(
            lambda: client.post("/v1/answer", json=answer_payload)
        )
        latencies.append(latency)
        answer_ok = answer.status_code == 200

        stream, latency = _request_latency_ms(
            lambda: client.post("/v1/answer/stream", json=answer_payload)
        )
        latencies.append(latency)
        stream_ok = (
            stream.status_code == 200
            and stream.headers.get("content-type", "").startswith("text/event-stream")
            and "event: final" in stream.text
        )

        gates, latency = _request_latency_ms(lambda: client.get("/v1/gates"))
        latencies.append(latency)
        gates_ok = gates.status_code == 200 and "overall_ok" in gates.json()

        ops_summary, latency = _request_latency_ms(
            lambda: client.get("/v1/ops/summary")
        )
        latencies.append(latency)
        ops_payload = ops_summary.json() if ops_summary.status_code == 200 else {}
        ops_ok = (
            ops_summary.status_code == 200
            and "eval" in ops_payload
            and "tools" in ops_payload
        )
        token_cost_recorded = (
            ops_ok
            and "estimated_total_tokens" in ops_payload["eval"]
            and "estimated_cost_usd" in ops_payload["eval"]
        )

        path_escape = client.get(
            "/v1/ops/summary",
            params={
                "eval_dir": str(root.parent),
                "audit_path": "artifacts/eval_agent/agent_artifacts/audit.jsonl",
            },
        )
        path_safety_ok = path_escape.status_code == 400

    metrics = {
        "healthz_pass": _pass_metric(healthz_ok),
        "answer_pass": _pass_metric(answer_ok),
        "stream_pass": _pass_metric(stream_ok),
        "gates_pass": _pass_metric(gates_ok),
        "ops_summary_pass": _pass_metric(ops_ok),
        "path_safety_pass": _pass_metric(path_safety_ok),
        "latency_p50_ms": round(statistics.median(latencies), 3),
        "latency_p95_ms": round(_percentile(latencies, 0.95), 3),
        "token_cost_distribution_recorded": _pass_metric(token_cost_recorded),
    }
    thresholds = {
        "healthz_pass": 1.0,
        "answer_pass": 1.0,
        "stream_pass": 1.0,
        "gates_pass": 1.0,
        "ops_summary_pass": 1.0,
        "path_safety_pass": 1.0,
        "latency_p50_ms": 0.0,
        "latency_p95_ms": 0.0,
        "token_cost_distribution_recorded": 1.0,
    }
    for key, threshold in thresholds.items():
        value = metrics[key]
        if key.startswith("latency_"):
            if value < threshold:
                failures.append(key)
        elif value != threshold:
            failures.append(key)

    summary = {
        "service_ops_complete": not failures,
        "docker_demo_command": "docker run --rm -p 8000:8000 rfp-rag-service:ci",
        "metrics": metrics,
        "thresholds": thresholds,
        "failed": failures,
        "smoke_question_length": len(question),
        "full_answer_smoke": full_answer,
        "full_gates_smoke": full_gates,
        "endpoint_count": 5,
    }
    _write_json(out, summary)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run credential-free Stage 2 service ops smoke checks."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--question", default="테스트 사업을 근거와 함께 요약해줘")
    parser.add_argument(
        "--full-answer",
        action="store_true",
        help="Exercise the real offline answer path instead of a lightweight endpoint smoke.",
    )
    parser.add_argument(
        "--full-gates",
        action="store_true",
        help="Exercise the full gate_status path through /v1/gates.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    summary = evaluate_service_ops(
        root=args.root,
        out=args.out,
        question=args.question,
        full_answer=args.full_answer,
        full_gates=args.full_gates,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["service_ops_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
