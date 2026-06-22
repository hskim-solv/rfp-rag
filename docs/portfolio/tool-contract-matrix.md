# Tool Contract Matrix

This matrix records the current tool and service contracts for senior AI Agent
Engineer review. It is not a hosted-production claim. Hosted auth, per-user
quotas, public dashboard access, and external telemetry remain approval-gated
scopes.

## Service Endpoints

| surface | schema | side effect | auth/rate-limit boundary | timeout/output cap | redaction/audit | error fields |
|---|---|---|---|---|---|---|
| `GET /healthz` | no input; `{"ok": true, "service": "rfp-rag"}` output | read-only | local/container reviewer mode; hosted token/rate limit not implemented | local runtime only | no sensitive payload | HTTP status |
| `POST /v1/answer` | `AnswerRequest` fields include `question`, `index_dir`, `provider`, `retrieval_mode`, `reranker`, `rerank_candidate_k`, `visual_candidates`, `visual_gate`; `AnswerResponse` returns answer, confidence, warnings, ids, scores | read-only answer generation over local index | `provider=offline`, `retrieval_mode=vector`, `reranker=none`; hosted auth/rate limit is non-claim | bounded by local request runtime; no provider calls in service mode | citations/ids are returned, not raw secrets | FastAPI validation plus guardrail `400` with `detail.code` |
| `POST /v1/answer/stream` | same request; SSE `status` then `final` on success | read-only streaming answer | same as `/v1/answer`; streaming budget is future hosted boundary | local SSE smoke only | streamed payload follows answer response policy | HTTP status/SSE event; explicit SSE `error` event remains future hosted hardening |
| `GET /v1/gates` | optional `root` query param constrained to repo root; local gate status output | read-only artifact inspection | local artifact boundary only | full gate path is required by `artifacts/service_ops/summary.json`; full smoke requires `overall_ok=true` | aggregate gate fields; no raw RFP source | HTTP status |
| `GET /v1/ops/summary` | artifact path params under allowed prefixes | read-only artifact summary | local artifact boundary only | local summary runtime; path traversal rejected | counts/cost estimates/tool summaries only | HTTP `400` on unsafe paths |

## MCP-style Ops Tools

| tool | input schema | output schema | side effect class | auth/rate-limit boundary | timeout/output cap | redaction policy | audit/error fields |
|---|---|---|---|---|---|---|---|
| `gate.status` | object with optional `root` string; `additionalProperties=false` | object requiring `overall_ok`, `lanes` | read-only | local reviewer process only; hosted auth/rate limit not implemented | descriptor `timeoutMs=30000`, `maxResponseBytes=200000`; runtime measures duration, enforces serialized response cap, and applies max tool-call budget | aggregate gate status only | `artifact_path_not_allowed`, `tool_not_allowed`, `tool_budget_exceeded`, `tool_timeout`, `tool_response_too_large`, `invalid_arguments` |
| `ops.summary` | object with `eval_dir`, `audit_path`, optional cost rates; `additionalProperties=false` | object requiring `eval`, `tools` | read-only | local reviewer process only | descriptor `timeoutMs=30000`, `maxResponseBytes=200000`; runtime enforces path safety, duration/response cap, and max tool-call budget | predictions summarized; audit args are pre-redacted | `artifact_missing`, `artifact_path_not_allowed`, `tool_not_allowed`, `tool_budget_exceeded`, `tool_timeout`, `tool_response_too_large`, `invalid_arguments` |
| `eval.metrics` | object with optional `eval_dir`; `additionalProperties=false` | metrics object | read-only | local reviewer process only | descriptor `timeoutMs=10000`, `maxResponseBytes=200000`; runtime enforces path safety, duration/response cap, and max tool-call budget | metrics only; no prediction bodies/source text | `metrics_missing`, `metrics_invalid_json`, `artifact_path_not_allowed`, `tool_not_allowed`, `tool_budget_exceeded`, `tool_timeout`, `tool_response_too_large`, `invalid_arguments` |

## Explicit Non-claims

- The current ops surface is an MCP-style JSONL shim, not full MCP transport,
  session negotiation, hosted auth, or capability negotiation.
- SQL-backed inspection is not implemented yet. A future SQL tool must expose
  named read-only views only, enforce `LIMIT`/timeout/output caps, and avoid raw
  RFP source text by default.
- Web search and internal API tools are intentionally absent from the local
  portfolio surface. The current workload is source-first RFP artifacts, so
  unbounded web/browser access would weaken publishability and reproducibility.
- Runtime descriptors now enforce local duration measurement and serialized
  response byte caps. Full hosted DoS controls still require separate
  implementation before public exposure.
