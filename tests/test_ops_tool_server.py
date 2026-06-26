from __future__ import annotations

import json
from pathlib import Path

import pytest

from rfp_rag.ops_tool_server import (
    TOOL_DESCRIPTORS,
    ToolGuardrailError,
    ToolRegistry,
    handle_request,
)


def _write_eval_fixture(path: Path) -> Path:
    eval_dir = path / "artifacts/eval"
    eval_dir.mkdir(parents=True)
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
    audit_path = path / "artifacts/eval_agent/agent_artifacts/audit.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
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
    assert response["result"]["tools"][0]["sideEffectClass"] == "read-only"
    assert "outputSchema" in response["result"]["tools"][1]
    assert "errorCodes" in response["result"]["tools"][2]


def test_ops_summary_tool_call_returns_observability_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
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
                    "eval_dir": str(eval_dir.relative_to(tmp_path)),
                    "audit_path": str(audit_path.relative_to(tmp_path)),
                },
            },
        }
    )

    assert response["id"] == "call-1"
    result = response["result"]
    assert result["tool"] == "ops.summary"
    assert result["audit"]["tool"] == "ops.summary"
    assert result["audit"]["status"] == "ok"
    assert result["audit"]["error_code"] is None
    assert result["content"]["eval"]["prediction_count"] == 1
    assert result["content"]["tools"]["total_calls"] == 1


def test_ops_summary_tool_rejects_artifact_path_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_audit_fixture(tmp_path)

    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "call-escape",
            "method": "tools/call",
            "params": {
                "name": "ops.summary",
                "arguments": {
                    "eval_dir": str(tmp_path.parent),
                    "audit_path": "artifacts/eval_agent/agent_artifacts/audit.jsonl",
                },
            },
        }
    )

    assert response["error"]["code"] == "artifact_path_not_allowed"


def test_tool_registry_rejects_tools_outside_allowlist() -> None:
    registry = ToolRegistry(allowed_tools={"gate.status"})

    with pytest.raises(ToolGuardrailError, match="tool_not_allowed"):
        registry.call_tool("ops.summary", {})


def test_tool_registry_enforces_max_tool_call_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    eval_dir = _write_eval_fixture(tmp_path)
    registry = ToolRegistry(max_tool_calls=1)

    registry.call_tool(
        "eval.metrics", {"eval_dir": str(eval_dir.relative_to(tmp_path))}
    )

    with pytest.raises(ToolGuardrailError, match="tool_budget_exceeded"):
        registry.call_tool(
            "eval.metrics", {"eval_dir": str(eval_dir.relative_to(tmp_path))}
        )


def test_tool_registry_enforces_response_byte_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    eval_dir = _write_eval_fixture(tmp_path)
    registry = ToolRegistry()
    descriptor = next(
        tool for tool in TOOL_DESCRIPTORS if tool["name"] == "eval.metrics"
    )
    old_cap = descriptor["maxResponseBytes"]
    descriptor["maxResponseBytes"] = 1
    try:
        with pytest.raises(ToolGuardrailError, match="tool_response_too_large"):
            registry.call_tool(
                "eval.metrics", {"eval_dir": str(eval_dir.relative_to(tmp_path))}
            )
    finally:
        descriptor["maxResponseBytes"] = old_cap
    assert registry.last_audit_record is not None
    assert registry.last_audit_record["status"] == "error"
    assert registry.last_audit_record["error_code"] == "tool_response_too_large"


def test_tool_call_rejects_unknown_arguments() -> None:
    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "bad-extra",
            "method": "tools/call",
            "params": {
                "name": "ops.summary",
                "arguments": {"unexpected": True},
            },
        }
    )

    assert response["error"]["code"] == "invalid_arguments"
    assert "unexpected" in response["error"]["message"]


def test_tool_call_rejects_bad_argument_types() -> None:
    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "bad-type",
            "method": "tools/call",
            "params": {
                "name": "ops.summary",
                "arguments": {"input_cost_per_1k": "not-a-number"},
            },
        }
    )

    assert response["error"]["code"] == "invalid_arguments"
    assert "input_cost_per_1k" in response["error"]["message"]


def test_eval_metrics_reports_missing_metrics_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "artifacts/eval_empty").mkdir(parents=True)

    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "missing-metrics",
            "method": "tools/call",
            "params": {
                "name": "eval.metrics",
                "arguments": {"eval_dir": "artifacts/eval_empty"},
            },
        }
    )

    assert response["error"]["code"] == "metrics_missing"


def test_eval_metrics_reports_invalid_metrics_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    eval_dir = tmp_path / "artifacts/eval_bad"
    eval_dir.mkdir(parents=True)
    (eval_dir / "metrics.json").write_text("{not json", encoding="utf-8")

    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "bad-metrics",
            "method": "tools/call",
            "params": {
                "name": "eval.metrics",
                "arguments": {"eval_dir": "artifacts/eval_bad"},
            },
        }
    )

    assert response["error"]["code"] == "metrics_invalid_json"


def test_ops_summary_reports_missing_eval_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    audit_path = _write_audit_fixture(tmp_path)

    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "missing-eval",
            "method": "tools/call",
            "params": {
                "name": "ops.summary",
                "arguments": {
                    "eval_dir": "artifacts/does_not_exist",
                    "audit_path": str(audit_path.relative_to(tmp_path)),
                },
            },
        }
    )

    assert response["error"]["code"] == "artifact_missing"


def test_ops_summary_reports_missing_audit_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    eval_dir = _write_eval_fixture(tmp_path)

    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "missing-audit",
            "method": "tools/call",
            "params": {
                "name": "ops.summary",
                "arguments": {
                    "eval_dir": str(eval_dir.relative_to(tmp_path)),
                    "audit_path": "artifacts/eval_agent/agent_artifacts/audit.jsonl",
                },
            },
        }
    )

    assert response["error"]["code"] == "artifact_missing"
