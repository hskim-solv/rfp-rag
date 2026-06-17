from __future__ import annotations

import json
from pathlib import Path

import pytest

from rfp_rag.ops_tool_server import ToolGuardrailError, ToolRegistry, handle_request


def _write_eval_fixture(path: Path) -> Path:
    eval_dir = path / "eval"
    eval_dir.mkdir()
    (eval_dir / "metrics.json").write_text(
        json.dumps({"provider_lane": "offline", "gate": {"ok": True}}),
        encoding="utf-8",
    )
    (eval_dir / "predictions.jsonl").write_text(
        json.dumps(
            {
                "query": "테스트 질의",
                "answer": "테스트 답변",
                "source_texts": ["근거"],
                "warnings": [],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return eval_dir


def _write_audit_fixture(path: Path) -> Path:
    audit_path = path / "audit.jsonl"
    audit_path.write_text(
        json.dumps(
            {
                "thread_id": "t1",
                "tool": "search_rfp",
                "args": {"query": "q"},
                "outcome": "1 results",
                "approved": None,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return audit_path


def test_tools_list_exposes_mcp_style_tool_descriptors() -> None:
    response = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert response["id"] == 1
    names = [tool["name"] for tool in response["result"]["tools"]]
    assert names == ["gate.status", "ops.summary", "eval.metrics"]
    assert response["result"]["tools"][0]["inputSchema"]["type"] == "object"


def test_ops_summary_tool_call_returns_observability_payload(tmp_path: Path) -> None:
    eval_dir = _write_eval_fixture(tmp_path)
    audit_path = _write_audit_fixture(tmp_path)

    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "call-1",
            "method": "tools/call",
            "params": {
                "name": "ops.summary",
                "arguments": {
                    "eval_dir": str(eval_dir),
                    "audit_path": str(audit_path),
                },
            },
        }
    )

    assert response["id"] == "call-1"
    result = response["result"]
    assert result["tool"] == "ops.summary"
    assert result["content"]["eval"]["prediction_count"] == 1
    assert result["content"]["tools"]["total_calls"] == 1


def test_tool_registry_rejects_tools_outside_allowlist() -> None:
    registry = ToolRegistry(allowed_tools={"gate.status"})

    with pytest.raises(ToolGuardrailError, match="tool_not_allowed"):
        registry.call_tool("ops.summary", {})


def test_tool_registry_enforces_max_tool_call_budget(tmp_path: Path) -> None:
    eval_dir = _write_eval_fixture(tmp_path)
    registry = ToolRegistry(max_tool_calls=1)

    registry.call_tool("eval.metrics", {"eval_dir": str(eval_dir)})

    with pytest.raises(ToolGuardrailError, match="tool_budget_exceeded"):
        registry.call_tool("eval.metrics", {"eval_dir": str(eval_dir)})
