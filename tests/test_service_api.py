from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from rfp_rag.service import app as service_app


def test_healthz_reports_service_ready() -> None:
    client = TestClient(service_app.create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "service": "rfp-rag"}


def test_answer_endpoint_returns_typed_rag_response(monkeypatch) -> None:
    seen: dict[str, Any] = {}

    def fake_answer_query(*args: Any, **kwargs: Any) -> dict[str, Any]:
        seen["args"] = args
        seen["kwargs"] = kwargs
        return {
            "answer": "근거 기반 답변",
            "confidence": "high",
            "warnings": [],
            "sources": [
                {
                    "doc_id": "doc:000",
                    "chunk_id": "doc:000:chunk:0",
                    "score": 0.9,
                    "project_name": "테스트 사업",
                }
            ],
            "retrieved_doc_ids": ["doc:000"],
            "retrieved_chunk_ids": ["doc:000:chunk:0"],
            "scores": [0.9],
            "reranker": "none",
            "rerank_candidate_k": 5,
        }

    monkeypatch.setattr(service_app, "answer_query", fake_answer_query)
    client = TestClient(service_app.create_app())

    response = client.post(
        "/v1/answer",
        json={
            "question": "테스트 사업 요약해줘",
            "index_dir": "artifacts/index",
            "provider": "offline",
            "top_k": 3,
            "min_score": 0.34,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "근거 기반 답변"
    assert body["sources"][0]["chunk_id"] == "doc:000:chunk:0"
    assert body["metadata"]["provider"] == "offline"
    assert seen["args"] == (Path("artifacts/index"), "테스트 사업 요약해줘")
    assert seen["kwargs"]["top_k"] == 3
    assert seen["kwargs"]["min_score"] == 0.34


def test_answer_stream_endpoint_emits_sse_events(monkeypatch) -> None:
    def fake_answer_query(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "answer": "스트리밍 답변",
            "confidence": "medium",
            "warnings": ["note"],
            "sources": [],
            "retrieved_doc_ids": [],
            "retrieved_chunk_ids": [],
            "scores": [],
            "reranker": "none",
            "rerank_candidate_k": 5,
        }

    monkeypatch.setattr(service_app, "answer_query", fake_answer_query)
    client = TestClient(service_app.create_app())

    response = client.post(
        "/v1/answer/stream",
        json={"question": "질문", "index_dir": "artifacts/index"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    chunks = response.text.strip().split("\n\n")
    assert chunks[0].startswith("event: status")
    assert "started" in chunks[0]
    assert chunks[-1].startswith("event: final")
    payload = json.loads(chunks[-1].split("data: ", 1)[1])
    assert payload["answer"] == "스트리밍 답변"


def test_gates_endpoint_returns_gate_status(monkeypatch, tmp_path: Path) -> None:
    def fake_collect_gate_status(root: Path) -> dict[str, Any]:
        return {
            "root": str(root),
            "overall_ok": True,
            "lanes": {"offline_rag": {"ok": True}},
        }

    monkeypatch.setattr(service_app, "collect_gate_status", fake_collect_gate_status)
    client = TestClient(service_app.create_app())
    response = client.get("/v1/gates", params={"root": str(tmp_path)})

    assert response.status_code == 200
    assert response.json()["overall_ok"] is True
    assert response.json()["root"] == str(tmp_path)
