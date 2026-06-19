from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TextIO

from rfp_rag.gate_status import collect_gate_status
from rfp_rag.ops_metrics import summarize_audit_log, summarize_eval_artifacts
from rfp_rag.path_safety import ArtifactPathError, safe_artifact_path


class ToolGuardrailError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


TOOL_DESCRIPTORS: list[dict[str, Any]] = [
    {
        "name": "gate.status",
        "description": "Read local gate_status evidence without mutating artifacts.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string", "default": "."}},
            "additionalProperties": False,
        },
    },
    {
        "name": "ops.summary",
        "description": "Summarize eval predictions and agent audit logs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "eval_dir": {"type": "string", "default": "artifacts/eval"},
                "audit_path": {
                    "type": "string",
                    "default": "artifacts/eval_agent/agent_artifacts/audit.jsonl",
                },
                "input_cost_per_1k": {"type": "number", "default": 0.0},
                "output_cost_per_1k": {"type": "number", "default": 0.0},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "eval.metrics",
        "description": "Read a local eval metrics.json artifact.",
        "inputSchema": {
            "type": "object",
            "properties": {"eval_dir": {"type": "string", "default": "artifacts/eval"}},
            "additionalProperties": False,
        },
    },
]


def _tool_descriptor(name: str) -> dict[str, Any]:
    for descriptor in TOOL_DESCRIPTORS:
        if descriptor["name"] == name:
            return descriptor
    raise ToolGuardrailError("unknown_tool", f"tool {name!r} is not registered")


def _validate_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    descriptor = _tool_descriptor(name)
    schema = descriptor["inputSchema"]
    properties = schema.get("properties", {})
    if not isinstance(arguments, dict):
        raise ToolGuardrailError(
            "invalid_arguments", "tool arguments must be an object"
        )
    unknown = sorted(set(arguments) - set(properties))
    if unknown and schema.get("additionalProperties") is False:
        raise ToolGuardrailError(
            "invalid_arguments", f"unknown argument(s): {', '.join(unknown)}"
        )
    for key, value in arguments.items():
        expected_type = (properties.get(key) or {}).get("type")
        if expected_type == "string" and not isinstance(value, str):
            raise ToolGuardrailError(
                "invalid_arguments", f"argument {key!r} must be a string"
            )
        if expected_type == "number" and (
            not isinstance(value, int | float) or isinstance(value, bool)
        ):
            raise ToolGuardrailError(
                "invalid_arguments", f"argument {key!r} must be a number"
            )
    return arguments


def list_tools() -> list[dict[str, Any]]:
    return TOOL_DESCRIPTORS


class ToolRegistry:
    def __init__(
        self,
        *,
        allowed_tools: set[str] | None = None,
        max_tool_calls: int = 20,
    ) -> None:
        self.allowed_tools = allowed_tools or {
            tool["name"] for tool in TOOL_DESCRIPTORS
        }
        self.max_tool_calls = max_tool_calls
        self.tool_call_count = 0

    def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if name not in self.allowed_tools:
            raise ToolGuardrailError(
                "tool_not_allowed", f"tool {name!r} is not in the allowlist"
            )
        if self.tool_call_count >= self.max_tool_calls:
            raise ToolGuardrailError(
                "tool_budget_exceeded",
                f"max tool-call budget {self.max_tool_calls} exceeded",
            )

        self.tool_call_count += 1
        args = _validate_arguments(name, arguments or {})

        if name == "gate.status":
            root = safe_artifact_path(
                Path(str(args.get("root", "."))), allowed_relatives=(".",)
            )
            return collect_gate_status(root)
        if name == "ops.summary":
            eval_dir = safe_artifact_path(
                Path(str(args.get("eval_dir", "artifacts/eval"))),
                allowed_prefixes=("artifacts",),
            )
            audit_path = safe_artifact_path(
                Path(
                    str(
                        args.get(
                            "audit_path",
                            "artifacts/eval_agent/agent_artifacts/audit.jsonl",
                        )
                    )
                ),
                allowed_prefixes=("artifacts",),
                expected_name="audit.jsonl",
            )
            if not eval_dir.exists() or not eval_dir.is_dir():
                raise ToolGuardrailError(
                    "artifact_missing", f"eval artifact directory not found: {eval_dir}"
                )
            for required_name in ("metrics.json", "predictions.jsonl"):
                required_path = eval_dir / required_name
                if not required_path.exists():
                    raise ToolGuardrailError(
                        "artifact_missing",
                        f"required eval artifact not found: {required_path}",
                    )
            if not audit_path.exists():
                raise ToolGuardrailError(
                    "artifact_missing", f"audit artifact not found: {audit_path}"
                )
            return {
                "eval": summarize_eval_artifacts(
                    eval_dir,
                    input_cost_per_1k=float(args.get("input_cost_per_1k", 0.0)),
                    output_cost_per_1k=float(args.get("output_cost_per_1k", 0.0)),
                ),
                "tools": summarize_audit_log(audit_path),
            }
        if name == "eval.metrics":
            eval_dir = safe_artifact_path(
                Path(str(args.get("eval_dir", "artifacts/eval"))),
                allowed_prefixes=("artifacts",),
            )
            metrics_path = eval_dir / "metrics.json"
            if not metrics_path.exists():
                raise ToolGuardrailError(
                    "metrics_missing", f"metrics artifact not found: {metrics_path}"
                )
            try:
                return json.loads(metrics_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ToolGuardrailError(
                    "metrics_invalid_json", f"invalid metrics JSON: {exc.msg}"
                ) from exc

        raise ToolGuardrailError("unknown_tool", f"tool {name!r} is not registered")


def _error_response(request_id: Any, code: str, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def handle_request(
    request: dict[str, Any], registry: ToolRegistry | None = None
) -> dict[str, Any]:
    request_id = request.get("id")
    method = request.get("method")
    tool_registry = registry or ToolRegistry()

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": list_tools()}}

    if method == "tools/call":
        params = request.get("params") or {}
        try:
            name = str(params["name"])
            arguments = params.get("arguments") or {}
            content = tool_registry.call_tool(name, arguments)
        except KeyError:
            return _error_response(request_id, "invalid_request", "missing tool name")
        except ArtifactPathError as exc:
            return _error_response(request_id, exc.code, exc.message)
        except ToolGuardrailError as exc:
            return _error_response(request_id, exc.code, exc.message)
        except ValueError as exc:
            return _error_response(request_id, "invalid_arguments", str(exc))
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tool": name, "content": content},
        }

    return _error_response(request_id, "method_not_found", f"unknown method {method!r}")


def serve_jsonl(
    lines: Iterable[str],
    output: TextIO,
    *,
    registry: ToolRegistry | None = None,
) -> int:
    tool_registry = registry or ToolRegistry()
    for line in lines:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = handle_request(request, tool_registry)
        except json.JSONDecodeError as exc:
            response = _error_response(None, "invalid_json", str(exc))
        output.write(json.dumps(response, ensure_ascii=False, sort_keys=True) + "\n")
        output.flush()
    return 0


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MCP-style JSONL tool server for local RFP RAG ops."
    )
    parser.add_argument(
        "--allow-tool",
        action="append",
        dest="allowed_tools",
        help="Allowed tool name. May be repeated. Defaults to all read-only ops tools.",
    )
    parser.add_argument("--max-tool-calls", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    registry = ToolRegistry(
        allowed_tools=set(args.allowed_tools) if args.allowed_tools else None,
        max_tool_calls=args.max_tool_calls,
    )
    return serve_jsonl(sys.stdin, sys.stdout, registry=registry)


if __name__ == "__main__":
    raise SystemExit(main())
