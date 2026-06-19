# RFP RAG System Architecture

This document is the architecture evidence map for the current repository. It
only describes implemented, locally verifiable surfaces; planned cloud/UI work is
called out separately in the boundary section.

## Logical Architecture

```mermaid
flowchart LR
  raw["Raw RFP corpus\n100 HWP/PDF files\nlocal data/files"]
  registry["CSV metadata registry\ndata/data_list.csv"]
  parsing["Source parsing\nrfp_rag.parse_sources\nrfp_rag.source_parsing"]
  quality["Parser quality + visual audit\nparser_quality_eval\nvisual_* lanes"]
  chunking["Section-aware chunking\nrfp_rag.chunking\nsection_detector"]
  index["Embedded Qdrant index\nrfp_rag.vector_index\nartifacts/index*"]
  rag["Citation-grounded RAG\nrfp_rag.rag_chain\nask.py"]
  agent["LangGraph agent lane\nroute/retrieve/grade/rewrite/generate/verify/HITL\nrfp_rag.agent"]
  service["FastAPI service\n/v1/answer\n/v1/answer/stream\n/v1/gates\n/v1/ops/summary"]
  ops["MCP-style ops tools\nrfp_rag.ops_tool_server\nJSONL tools/list + tools/call"]
  evals["Evaluation gates\nrfp_rag.evaluate\nrfp_rag.agent.evaluate_agent\nrfp_rag.gate_status"]
  reports["Evidence artifacts\nREADME.md\nREPORT.md\nartifacts/*"]

  raw --> parsing
  registry --> parsing
  parsing --> quality
  parsing --> chunking
  chunking --> index
  index --> rag
  rag --> agent
  rag --> service
  agent --> service
  evals --> reports
  rag --> evals
  agent --> evals
  quality --> evals
  evals --> service
  evals --> ops
  service --> reports
  ops --> reports
```

## Runtime Surfaces

```mermaid
flowchart TB
  user["User / evaluator"]
  api["FastAPI\nrfp_rag.service.app"]
  guard["Question guardrail\nrfp_rag.guardrails"]
  threadpool["Threadpool bridge\nblocking RAG in async API"]
  rag["answer_query\nrfp_rag.rag_chain"]
  vector["Qdrant local store\nartifacts/index"]
  visual["Optional visual sidecar\nvisual candidates + gate"]
  gates["Gate status\nrfp_rag.gate_status"]
  obs["Ops metrics\nrfp_rag.ops_metrics"]
  toolserver["JSONL ops tool server\nallowlist + max calls"]

  user -->|POST /v1/answer| api
  user -->|POST /v1/answer/stream| api
  api --> guard
  guard --> threadpool
  threadpool --> rag
  rag --> vector
  rag --> visual
  user -->|GET /v1/gates| api
  api --> gates
  user -->|GET /v1/ops/summary| api
  api --> obs
  user -->|tools/list tools/call| toolserver
  toolserver --> gates
  toolserver --> obs
```

## Agent Workflow

```mermaid
stateDiagram-v2
  [*] --> route
  route --> retrieve: RAG query
  route --> tool_exec: metadata query
  retrieve --> grade
  grade --> rewrite: weak retrieval and rewrite_count < 2
  rewrite --> retrieve
  grade --> generate: sufficient evidence
  grade --> respond: weak retrieval and rewrite_count >= 2
  tool_exec --> generate
  generate --> verify
  verify --> save_report: save requested
  verify --> respond: no save requested
  save_report --> respond: HITL approve/reject
  respond --> [*]
```

Implemented evidence:

| architecture point | repo evidence | local gate |
|---|---|---|
| typed state | `rfp_rag/agent/state.py` | `tests/test_agent_graph.py` |
| conditional edges | `rfp_rag/agent/graph.py` | `agent_lane_complete` |
| retry/reflection loop | `grade -> rewrite -> retrieve`, max rewrite count | `loop_termination=1.0` |
| checkpointer | `sqlite_checkpointer()` and test `MemorySaver` | CLI resume tests |
| HITL approval | `interrupt()` in `save_report_node` | approve/reject graph tests |
| tool audit | `AuditLogger` JSONL with redacted query-like args | `artifacts/eval_agent/agent_artifacts/audit.jsonl` |

## Evaluation And Evidence Flow

```mermaid
flowchart LR
  offline["offline RAG lane\ncredential-free"]
  real["real_openai RAG lane\nexplicit cost approval"]
  agent["agent offline lane\nLangGraph workflow"]
  visual["visual candidate gate\nreviewed sidecar evidence"]
  guard["guardrail regression\nprompt injection + secrets"]
  ci["GitHub Actions\nsynthetic corpus\npytest -m not real"]
  status["gate_status\noverall_ok"]

  offline --> status
  real --> status
  agent --> status
  visual --> status
  guard --> ci
  ci --> status
```

Current local gate files:

| lane | artifact | status evidence |
|---|---|---|
| offline RAG | `artifacts/eval/metrics.json` | `offline_scaffold_complete=true` |
| real RAG | `artifacts/eval_real/metrics.json` | `rag_quality_complete=true` under `rfp-rag-real-v6` with parsed-source lineage and hard-slice floors |
| agent offline | `artifacts/eval_agent/metrics.json` | `agent_lane_complete=true` |
| visual candidate | `artifacts/visual_tesseract_candidate_expanded_gate/summary.json` | `ok=true` |
| guardrails | `artifacts/guardrails/summary.json` | `guardrail_regression_complete=true` |

## Operational Boundaries

- `data/` and `artifacts/` are local evidence and are intentionally gitignored.
- GitHub Actions uses a synthetic corpus; it proves credential-free regression,
  not private corpus publication.
- Docker image excludes raw RFP files and local artifacts; mount them read-only
  for answer/gate endpoints.
- `real_openai` evaluation remains cost-bearing and must be explicitly approved.
- The MCP-style server is read-only JSONL tooling, not full MCP transport/auth.
- Service and ops tool paths are limited to approved repository artifact
  locations; arbitrary local path reads are rejected.
- No public cloud deployment, auth/session/rate-limit layer, live-traffic SLO,
  or broad public dashboard is claimed yet. The service evidence is a
  local/container contract smoke over the RAG and gate surfaces.

## Verification Commands

```bash
uv run pytest -m "not real"
uv run python -m rfp_rag.report_check --eval artifacts/eval --readme README.md
python3 -m rfp_rag.gate_status
python3 -m rfp_rag.guardrail_eval --cases tests/fixtures/guardrail_cases.jsonl --out artifacts/guardrails/summary.json
```
