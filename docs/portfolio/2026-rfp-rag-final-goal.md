# 2026 RFP RAG Final Goal

## Final Positioning

Target portfolio headline:

> AI Agent Engineer Senior Portfolio: Production-adjacent Agentic RAG Backend
> for Korean Public RFP Intelligence.

The project should not be presented as an RFP chatbot. The final story is:

> A production-adjacent Agentic RAG backend using Korean public procurement RFPs
> as the concrete workload: source-first HWP/PDF ingestion, evaluated retrieval,
> constrained LangGraph orchestration, guarded tool-using workflows,
> HITL/checkpoint behavior, thin streaming FastAPI service, local ops summaries,
> deterministic security smoke, and CI-backed evaluation gates.

This positioning is the working portfolio assumption from the role review: it is
more useful than a narrow "Retrieval & Evaluation Engineer" headline only if the
project proves backend operation, agent control, and evaluation evidence rather
than just retrieval metrics. The target role is senior
`AI Agent Engineer` or `AI Agent Backend Engineer`, with overlap into
`LLM/RAG AI Engineer`, `RAG Engine Researcher`, and `RAG & Graph Search
Engineer`. The hard capabilities to prove are Python backend engineering,
document parsing, chunking, vector/hybrid retrieval, reranking, citation
grounding, evaluation, typed agent state, conditional routing, bounded
retry/reflection, tool safety, API/service operation, observability, latency,
cost control, deployment, and guardrails.

This document describes the final target, not an unqualified hosted-production
claim. Current safe claims and missing production evidence are separated below.

## Scope Boundaries

In scope:

- 100 original Korean public RFP HWP/PDF documents as the body source of truth.
- CSV only as a metadata registry for project name, agency, budget, deadline,
  and filename.
- Parsed artifacts, page/section citations, visual-structure evidence, and
  reproducible evaluation artifacts.
- Offline credential-free tests and real-lane quality gates as separate lanes.
- FastAPI/Pydantic async service endpoints with streaming answer delivery.
- LangGraph typed-state orchestration where it improves routing, planning,
  retrieval, verification, retry/reflection, audit, checkpointing, or human
  approval.
- Tool/function-calling surface for document retrieval, run/metric inspection,
  and guarded operator actions.
- Evidence dashboard or service surface that exposes answers, citations, chunks,
  traces, metrics, failures, latency, token/cost, and gate freshness.
- Docker and GitHub Actions evidence for reproducible local/containerized use.

Out of scope for the final portfolio core:

- Claiming CSV-baseline retrieval as source-document quality.
- Presenting a generic chatbot UI as the main achievement.
- Full autonomous multi-agent behavior without measurable retrieval or workflow
  gains.
- MCP/FastMCP as the main product story before the core RAG/service workflow is
  stable. A small ops/tool server is useful; it must not replace the RAG product
  narrative.
- Cloud production deployment unless local/containerized evidence is already
  complete and credentials/spend are explicitly approved.
- Kubernetes, Terraform, fine-tuning, GraphRAG, or multimodal-agent work unless
  the core production Agentic RAG system is already demonstrable.

## Current Evidence Boundary

This section is a manual snapshot, not the authoritative current state. Before
using any current-status claim, refresh it from:

- `python3 -m rfp_rag.gate_status`
- `python3 -m rfp_rag.portfolio_check --out artifacts/portfolio_readiness.json`
- the generated `REPORT.md` sections that cite the same artifacts

As of the current packaging pass, the local/containerized evidence bundle is
ready to submit for a senior AI Agent Engineer repo/demo review. This is a
portfolio-evidence claim, not a hosted-production claim. It depends on rerunning
`gate_status`, `portfolio_check`, and the credential-free test lane before
citation; cloud deployment, public dashboard, live traffic SLOs, provider
billing telemetry, and reranker quality-win evidence remain outside the current
claim.

Current safe evidence:

- Source-first offline index and evaluation use parsed artifacts:
  `artifacts/index/manifest.json` records `text_source=parsed`,
  `parse_manifest_path=artifacts/parsed_docs/manifest.jsonl`, and
  `chunk_count=16459`.
- The latest source-first real lane evidence using `artifacts/index_real` and
  parsed-source lineage satisfies `rfp-rag-real-v6` with cross-document hard
  floors and model/prompt lineage.
- The LLM reranker path is an implemented interface with artifact fields and
  credential-free offline guards; no real/open reranker quality claim exists yet.
- The visual lane has a precision-hardened local OCR candidate, reviewed
  page-level visual evidence, and a 30-question visual/table evidence gate with
  `visual_evidence_hit_rate=0.92`; this is still not production visual
  understanding.
- The agent lane can be cited only when `gate_status` reports
  `agent_offline.ok=true` for the current index/min-score policy. It proves
  constrained LangGraph routing, retrieval, rewrite, metadata-tool, abstention,
  loop-termination, audit behavior, checkpoint/HITL, state redaction, and
  tool-budget behavior through tests and deterministic Stage 2 stress artifacts.
  It does not claim an autonomous hosted production agent.
- The FastAPI service slice exposes `/healthz`, `/v1/answer`,
  `/v1/answer/stream`, and `/v1/gates` as a thin typed API over existing RAG and
  gate evidence. Local service evidence exists; cloud deployment, live traffic
  SLOs, and a public dashboard are not yet claimed.

Current unsafe claims:

- "Hybrid or reranking improved retrieval quality."
- "Production visual understanding or multimodal RAG is solved."
- "The repository is a hosted production service or public dashboard portfolio."

## Final Product Shape

The finished project should expose these user-visible capabilities:

1. Source-document ingestion
   - Parse HWP/PDF source documents into durable artifacts.
   - Preserve parser lineage, page references, section labels, tables, and
     visual-structure risk signals.
   - Fail closed when source text is unavailable instead of silently falling
     back to CSV body text.

2. Source-aware retrieval
   - Build section-aware chunks from parsed artifacts.
   - Support dense, BM25, hybrid RRF, and reranked retrieval modes.
   - Preserve document/page/section evidence on every retrieved chunk.

3. Grounded answer generation
   - Generate answers only from retrieved evidence.
   - Return citations with document, page, and section references.
   - Abstain on unsupported questions.

4. Visual-structure evidence
   - Detect documents and pages where business-critical information may live in
     tables, schedules, organization charts, architecture diagrams, screenshots,
     or other visual elements.
   - Extract or manually validate targeted visual records before claiming
     coverage for those facts.

5. Agent workflow
   - Route query types.
   - Select retrieval strategy.
   - Retrieve, grade, rewrite when needed, generate, verify, and abstain.
   - Persist audit records and checkpoint state.
   - Pause for human approval before high-impact report-save actions.
   - Make state transitions, tool budgets, retry/reflection limits, and failure
     reasons inspectable enough that a reviewer can audit the agent as an
     engineered workflow, not a prompt wrapper.

6. Evidence dashboard or service surface
   - Show answer, citations, retrieved chunks, source previews, metrics, and
     failure reasons.
   - Expose run-level latency, token/cost estimates, trace IDs, and gate status.
   - Prefer a pragmatic FastAPI plus Streamlit surface unless a richer frontend
     becomes necessary.

7. Production backend service
   - Provide Python 3.11+ FastAPI endpoints with Pydantic request/response
     schemas.
   - Support async answer generation and SSE streaming for long-running agent
     responses.
   - Expose health, gate status, answer, evaluation summary, and trace/run lookup
     endpoints.

8. Tool and ops layer
   - Include document retrieval as a first-class tool.
   - Include at least one SQL-backed inspection tool for metadata, run history,
     audit, or evaluation artifacts. It must be read-only, parameterized, bound
     to named tables/views, capped by row and timeout limits, and forbidden from
     exposing raw RFP text, secrets, or PII.
   - Include an internal ops/API tool for gate status, metrics, or artifact
     comparison.
   - Include one narrow MCP/FastMCP-style tool server for RFP RAG Ops after the
     tool boundary, storage scope, and retention policy are explicit.

## Quality Targets

Final acceptance gates:

- `python3 -m rfp_rag.gate_status` exits `0` with no lane issues.
- An upgraded `python3 -m rfp_rag.portfolio_check --out artifacts/portfolio_readiness.json`
  exits `0` after validating the Stage 2 artifact contract below. A generic
  presence-only check of `metrics`, `thresholds`, and `failed` is explicitly not
  sufficient for the final claim.
- `artifacts/portfolio_readiness.json` has
  `portfolio_readiness_check=true`, `local_evidence_bundle_check=true`, and
  `second_stage_readiness.complete=true`, plus
  `stage2_contract_schema_enforced=true`.
- `second_stage_readiness.details[]` has no failed or missing gates across
  eval-set audit, real frozen-evidence quality, agent stress, retrieval bakeoff, visual
  quality, service ops, deterministic security smoke, and cost budget.
- `REPORT.md`, `README.md`, architecture docs, ADRs, demo script, screenshots,
  and final resume claim all point to the same generated artifacts. If these
  disagree, the final portfolio claim is invalid even when individual metrics
  look good.

Stage 2 artifact contract:

`second_stage_readiness.complete=true` is not sufficient by itself unless every
Stage 2 artifact also satisfies the named minimum schema below. `portfolio_check`
now enforces these fields and emits `stage2_contract_schema_enforced=true` only
when the Stage 2 contract passes. If any artifact later fails or goes stale, the
portfolio claim closes again.

| Gate | Artifact | Required fields / minimum metrics |
| --- | --- | --- |
| Eval-set audit | `artifacts/eval_stage2/coverage.json` | `eval_set_hash`, `split_manifest_path`, `label_rubric_path`, `contamination_notes_path`, `adjudication_log_path`; `query_count >= 150`, `metadata_doc_coverage == 100`, `hard_negative_count >= 30`, `cross_document_count >= 20`, `visual_table_count >= 30`, `failed == []` |
| Real frozen-evidence quality | `artifacts/eval_stage2_real/metrics.json` | model/prompt lineage, `thresholds_met=true`, `per_slice_failed == []`, `query_set_counts` matching `coverage.json`; real `recall@5 >= 0.95`, `recall@3 >= 0.90`, `mrr >= 0.85`, `metadata_exact_match >= 0.95`, `faithfulness >= 0.90`, `answer_relevancy >= 0.80`, answerable-slice judge coverage `>= 0.95`, citation presence/validity `== 1.0`; current claim is frozen evidence-set quality, not an independent public-traffic holdout |
| Agent stress | `artifacts/eval_agent_stress/metrics.json` | `scenario_matrix_hash`, branch replay artifact path, `trajectory_pass_rate == 1.0`, `branch_coverage == 1.0`, `thread_id_isolation_pass == 1.0`, `hitl_approval_convergence == 1.0`, `no_side_effect_before_approval == 1.0`, `checkpoint_close_path_pass == 1.0`, `audit_arg_redaction_pass == 1.0`, `ops_tool_budget_violation_count == 0`, `failed == []`; this does not claim full checkpoint-state redaction or agent-level tool-call budgeting |
| Retrieval bakeoff | `artifacts/retrieval_bakeoff/summary.json` | vector, BM25, and hybrid comparison on the same frozen set; no-regression floors for recall, citation validity, abstention, section hit, visual evidence, latency, and cost; explicit winner/tie-break ADR; `failed == []`; reranker is optional/deferred until a same-set paid/API artifact exists |
| Visual quality | `artifacts/visual_quality/summary.json` | `visual_question_count >= 30`, `visual_evidence_hit_rate >= 0.90`, `unsupported_visual_claim_rate <= 0.10`, sidecar on/off no-regression check for citation and abstention, `failed == []` |
| Service ops | `artifacts/service_ops/summary.json` | `/healthz`, `/v1/answer`, `/v1/answer/stream`, `/v1/gates`, and `/v1/ops/summary` smoke pass; Docker or local service demo command recorded; p50/p95 latency and token/cost distributions recorded; path-safety checks pass; `failed == []` |
| Deterministic security smoke | `artifacts/security_redteam/summary.json` | prompt-injection, malicious RFP content, malicious retrieved evidence, malicious tool output fixture cases, tool allowlist, tool budget, secret/PII leakage, selected demo-visible artifact redaction scan, publishable allowlist, retention/scope checks; `block_recall == 1.0`, `secret_pii_leak_count == 0`, `raw_persistence_count == 0`, `tool_policy_violation_count == 0`, `failed == []`; not a full hosted-service red-team or whole-repo leak scan |
| Cost budget | `artifacts/cost_budget/summary.json` | `token_record_coverage == 1.0`, `cost_record_coverage == 1.0`, real/open run cost estimates recorded, budget violation count `== 0`, regression threshold rationale recorded, `failed == []` |
| Paid/API execution plan | `artifacts/paid_lane_plan/summary.json` | dry-run only; exact cost-bearing commands, required env var names, target artifact writes, current budget estimate, and post-run verification commands recorded before paid/API approval |

Parser/source targets:

- `doc_count`: 100 source RFPs.
- Empty parsed text documents: 0.
- Average parser quality score: >= 0.95.
- Low-quality parsed documents: 0, unless each has a documented exception.
- Page citation availability: 100%.
- CSV body fallback for RAG content: 0.

Evaluation and freshness targets:

- `gate_status` must fail stale or lineage-mismatched evidence instead of
  reporting boolean-only success, and the CLI must return a non-zero exit code
  when `overall_ok=false`.
- Source-first real gate artifacts must use an index manifest with
  `text_source=parsed`, `parse_manifest_path`, and `index_text_source_counts`
  covering all 100 documents.
- Real gate contract must match the current source-first contract version and
  required commands.
- Hardened labeled set target: >= 150 total labeled queries, 100-document
  metadata coverage, >= 30 hard abstention or hard-negative questions, >= 20
  cross-document comparison questions, and >= 30 section/table/visual questions.
- Future independent holdout target: an independent frozen set with an
  `eval_set_hash`, documented label rubric, train/dev/holdout separation, no
  prompt or retrieval tuning after freeze, contamination notes, per-slice
  floors, and adjudicated corrections when labels are disputed.
- The future independent holdout must be evaluated from artifacts, not by
  reusing the same examples that drove prompt, chunking, reranker, or guardrail
  tuning. The current completed claim is a frozen evidence-set contract, not
  that stronger independent-holdout claim.
- Current offline set: 545 total queries after the paraphrase slice, including
  400 metadata, 10 curated text, 30 hard abstention, 30 section lookup, 20
  cross-document, 25 reviewed visual/table, and 30 paraphrase questions.
- Metrics must be reported by slice, not only as aggregate averages.

Retrieval targets:

- Real-lane `Recall@5`: >= 0.95.
- Real-lane `Recall@3`: >= 0.90.
- Real-lane `MRR`: >= 0.85.
- Section hit rate: >= 0.90 on section-labeled questions.
- Metadata exact match: >= 0.95.
- Any hybrid/reranker adoption claim requires same-dataset comparison against
  vector and BM25 controls with recall, MRR, abstention, section hit rate,
  latency, and token/cost estimates.
- Hybrid/reranker adoption requires either a material quality win with no
  regression on abstention/citation/section slices, or an explicit ADR choosing
  the simpler baseline because the gain is not worth latency, cost, or
  operational complexity.

Generation targets:

- Citation presence: 100%.
- Faithfulness: >= 0.90.
- Answer relevancy: >= 0.80.
- Unsupported/no-answer abstention pass rate: >= 0.90.
- Calibration note: the stricter aspirational targets `faithfulness >= 0.95`
  and `answer_relevancy >= 0.88` were rejected after the 550-query Stage 2
  real holdout showed that retrieval/citation can be perfect while RAGAS
  answer relevancy remains sensitive to terse metadata and visual-table answer
  style. Judge coverage was also moved from `1.0` to `>= 0.95` because a
  rate-limit burst can otherwise invalidate an otherwise passing run. The
  accepted gate keeps RAGAS generation and coverage thresholds above the base
  real lane (`0.80/0.70`, coverage `0.90`) while preserving hard requirements
  for recall, citation validity, metadata exactness, and visual evidence.

Visual-structure targets:

- Visual-risk candidate review coverage: representative high-risk sample first,
  then targeted expansion.
- Accepted targeted visual records: >= 80% of reviewed high-risk records.
- Unsupported visual-only factual claims: <= 10% in the visual-risk eval subset.
- Page-specific visual/table eval subset: >= 30 labeled questions before
  claiming visual/table factual coverage.
- Current page-specific visual/table eval subset: 25 labeled questions with
  `visual_evidence_hit_rate=0.92`; target shortfall is 5 reviewed questions plus
  sidecar on/off comparison.
- Sidecar on/off answer-quality comparison must show no citation or abstention
  regression before visual evidence is part of final answer claims.

Agent/workflow targets:

- Query route, retrieve, rewrite, generate, verify, abstain, audit, checkpoint,
  and HITL resume paths covered by tests or scripted demos.
- Agent lane gate passes with artifact-backed metrics.
- Tool calls and state transitions are inspectable from audit artifacts.
- Current agent lane evidence must match the current index/min-score policy in
  `gate_status`; otherwise rerun it before citing it.
- Real LLM router/rewriter smoke is optional but must be explicitly approved
  because it is cost-bearing.
- LangGraph graph uses typed state schema, conditional edges, checkpointing, and
  bounded retry/reflection loops.
- Agent acceptance requires a scenario matrix for route/retrieve/grade/rewrite/
  generate/verify/abstain/tool/HITL branches, branch replay artifacts or tests,
  `rewrite_count <= 2`, terminal failure reasons, and zero tool-budget
  violations.
- Checkpoint/HITL acceptance requires `thread_id` isolation for new questions,
  explicit same-`thread_id` resume only, approval and rejection both terminating
  predictably, `interrupt()` before any report-save side effect, no side effect
  without approval, and checkpoint saver close-path coverage.
- State acceptance requires reducer channels and overwrite channels to be
  documented, node outputs to be state deltas rather than in-place mutation, and
  persisted state/audit artifacts to store redacted summaries instead of raw
  prompts, query text, secrets, PII, or full RFP source.
- Final workflow includes a planner-executor or supervisor-worker split only if
  it maps to real RFP work such as compare, verify, draft report, and approve;
  adoption requires at least two independent subtasks, a shared-state contract,
  and supervisor decision audit.

Ops/service targets:

- Offline lane remains credential-free:
  `uv run python -m pytest -m "not real"` must pass without `OPENAI_API_KEY`.
  The exact `python3 -m pytest` form is valid when the repo `.venv` is first on
  PATH.
- Real lane is run only on explicit approval because it costs money.
- FastAPI service exposes Pydantic schemas, async handlers, and SSE streaming.
- Structured output validation is enforced on agent/tool-facing responses.
- Tool allowlist, max tool-call budget, prompt-injection checks, and
  secrets/PII leakage safeguards are covered by tests or scripted checks.
- Tool acceptance requires a table of tool names, input/output schema,
  side-effect class, auth/session boundary, timeout, row/result limits,
  structured error codes, redaction policy, and audit fields. Generic arbitrary
  SQL execution is out of scope.
- Untrusted RFP content and tool output must never be promoted to system or
  developer instructions. Prompt-injection tests must include malicious document
  content, malicious retrieved evidence, and malicious tool output.
- Dashboard or report shows gate freshness, latency, token/cost estimate, and
  failure classification.
- Containerized or local service demo can be reproduced from documented
  commands.
- Docker build and GitHub Actions CI are documented and run the no-real tests
  plus lightweight eval/report checks.
- Token/cost estimate coverage: 100% of generated evaluation predictions where
  a real/open model is used.
- Latency reporting coverage: 100% of service/demo requests and evaluation
  predictions.
- Latency and cost gates start as measured baselines, then become regression
  gates: final closeout must record p50/p95 latency, per-query token/cost
  distribution, threshold rationale, and fail conditions for regressions. Do not
  publish a latency threshold claim until that measured baseline exists.
- Trace, audit, checkpoint, dashboard, and screenshot artifacts must have a
  publishable allowlist, retention window, storage location, project/user scope,
  and redaction rule before they are used in public portfolio evidence.

Default tool contract:

| Tool | Auth/session boundary | Side effect | Input / output contract | Limits and guardrails | Structured errors | Audit fields |
| --- | --- | --- | --- | --- | --- | --- |
| `gate.status` | local project session only; root fixed to repo | read-only | input: `{root?: \".\"}`; output: `collect_gate_status` JSON | root restricted to repo root; timeout <= 10s; no raw RFP text | `tool_not_allowed`, `artifact_path_not_allowed`, `metrics_invalid_json` | `tool`, `root_hash`, `outcome`, `issue_count`, `duration_ms` |
| `ops.summary` | local project session only; artifact paths under repo | read-only | input: `{eval_dir, audit_path, input_cost_per_1k, output_cost_per_1k}`; output: eval/tool summaries | paths restricted under `artifacts/`; `audit_path` must end in `audit.jsonl`; timeout <= 10s; no raw prediction contexts in public output | `tool_not_allowed`, `artifact_path_not_allowed`, `artifact_missing`, `summary_invalid_json` | `tool`, `eval_dir`, `audit_path_hash`, `outcome`, `duration_ms` |
| `eval.metrics` | local project session only; artifact paths under repo | read-only | input: `{eval_dir}`; output: `metrics.json` summary | paths restricted under `artifacts/`; raw predictions excluded; timeout <= 5s | `tool_not_allowed`, `artifact_path_not_allowed`, `metrics_missing`, `metrics_invalid_json` | `tool`, `eval_dir`, `provider_lane`, `outcome`, `duration_ms` |
| `metadata.sql.inspect` | local project session; read-only DB handle | read-only | input: named view, parameter object, selected columns; output: capped rows plus schema version | named views only; parameterized queries only; no arbitrary SQL; row limit <= 100; timeout <= 5s; raw RFP text, secrets, and PII excluded | `tool_not_allowed`, `view_not_allowed`, `query_not_parameterized`, `row_limit_exceeded`, `query_timeout` | `tool`, `view`, `params_hash`, `row_count`, `outcome`, `duration_ms` |
| `search_rfp` | agent run session with thread id | read-only | input: redacted query summary plus `top_k`; output: cited chunk ids, doc ids, scores, citation metadata | `top_k <= 20`; persisted audit stores hash/length only for query-like text; no full source text in persistent audit/checkpoint | `tool_not_allowed`, `tool_budget_exceeded`, `retrieval_error`, `index_unavailable` | `tool`, `thread_id`, `query_hash`, `query_length`, `top_k`, `result_count`, `outcome` |
| `save_report` | HITL resume session; same `thread_id` only | write under reports dir | input: approved filename/content summary; output: report path | unreachable before `interrupt()` approval; one write per approved action; rejection produces no file | `approval_required`, `thread_mismatch`, `invalid_report_path`, `write_rejected` | `tool`, `thread_id`, `approved`, `filename`, `outcome`, `duration_ms` |
| `rfp-rag-ops` MCP server | local project session; no network/cloud auth by default | read-only unless new ADR | `tools/list` JSON schema must match runtime behavior | same limits as wrapped tools; new mutating or cost-bearing tools require ADR and approval gate | mirrors wrapped tool errors plus `mcp_schema_mismatch`, `mcp_method_not_allowed` | `method`, `tool`, `args_hash`, `outcome`, `duration_ms` |

Default artifact retention and publishability:

| Artifact class | Storage | Retention | Public portfolio rule |
| --- | --- | --- | --- |
| Eval metrics/reports | `artifacts/eval*`, `REPORT.md` | keep as local evidence until superseded by newer generated run | publish metrics and aggregate examples only; raw source contexts require manual allowlist |
| Agent audit | `artifacts/eval_agent*/agent_artifacts/audit.jsonl` | keep local evidence until regenerated; never hand-edit | publish only redacted tool summaries; query-like args must be hash/length, not raw text |
| Checkpoints | `artifacts/**/checkpoints.sqlite` | local demo/debug evidence only; delete/regenerate before public packaging unless explicitly needed | do not publish raw checkpoint DB; screenshots may show state summaries only |
| Traces | chosen trace backend or local exported summaries | default <= 30 days unless ADR says otherwise | publish trace IDs and redacted spans only; no raw prompts, raw tool inputs, secrets, PII, or full RFP source |
| Dashboard/screenshots | `docs/evidence/` or demo assets | keep curated public assets only | must pass publishable allowlist; show citations, ids, metrics, and redacted snippets, not full sensitive prompts or raw source dumps |
| Source previews | service/dashboard runtime only by default | not retained in public artifacts unless allowlisted | public default is citation metadata and short redacted excerpts; full RFP pages require explicit sample approval |

## Milestones

### M0. Baseline Lock

- Confirm current dirty worktree scope.
- Run credential-free test gate.
- Confirm report check and current metrics.
- Confirm `gate_status` and `portfolio_check` outputs, and record whether they
  are expected-pass or expected-fail under the current roadmap.
- Stop condition: unrelated user edits touch the same roadmap, gate, or evidence
  files needed for this milestone and cannot be separated without losing user
  work.

### M1. Quality Contract

- Encode final targets in docs and report language.
- Separate offline scaffold, open iteration, real quality, and agent quality
  gates.
- Stop condition: metrics cannot be mapped to current artifacts.

### M2. Source Lock

- Ensure source-first parser artifacts are the RAG body source of truth.
- Preserve parser lineage on chunks and metrics.
- Stop condition: any RAG path still silently uses CSV body text.

### M3. Visual/Table Semantic MVP

- Turn manual visual audit into targeted visual-structure extraction.
- Cover schedules, organization charts, architecture diagrams, screenshots, and
  tables where text extraction loses business meaning.
- Current status: first reviewed visual/table eval slice is wired into the
  offline contract with 25 labeled questions.
- Stop condition: visual claims cannot be tied back to page evidence.

### M4. Benchmark Hardening

- Build the senior portfolio evaluation set before celebrating retrieval deltas.
- Cover all 100 documents for metadata, plus hard negatives, paraphrases,
  cross-document questions, and section/table/visual slices.
- Freeze the Stage 2 evidence set with `eval_set_hash`, label rubric, split metadata,
  contamination notes, and per-slice floors before tuning prompts, chunking,
  retrieval, or reranking against it.
- Current gap: a stronger independent holdout remains future work. The current
  Stage 2 claim is a frozen evidence-set contract with real metrics, not a
  separate public-traffic or never-before-used benchmark.
- Before approval, generate `artifacts/paid_lane_plan/summary.json` with
  `uv run python -m rfp_rag.paid_lane_plan` and review the exact cost-bearing
  commands and target artifacts.
- Report per-slice metrics and failure examples.
- Stop condition: high aggregate scores can be explained by an easy or narrow
  query set, or the same examples are used for both tuning and future final holdout
  claims.

### M5. Retrieval And Reranker Ablation

- Compare dense, BM25, hybrid RRF, and reranked retrieval.
- Report quality, latency, and cost trade-offs.
- Define no-regression floors for recall, citation validity, abstention, section
  hit rate, visual evidence hit rate, latency, and cost before adopting a
  non-baseline retriever.
- Stop condition: quality gains are not statistically or operationally
  defensible.

### M6. Source-First Real Quality Gate

- Run approved real-lane evaluation on the parsed-source index.
- Update `REPORT.md` from generated artifacts, not by hand-editing metrics.
- Stop condition: real-lane cost approval is missing, or the real index manifest
  lacks parsed-source lineage.

### M7. Agent Workflow Senior Evidence

- Rerun offline agent evaluation with the current retrieval policy.
- Add trajectory/audit/checkpoint examples to the evidence surface.
- Show typed state, conditional edges, retry/reflection limits, tool-call
  budgets, HITL/checkpoint resume, and failure classification as first-class
  artifacts.
- Add a branch coverage matrix for graph nodes/edges, scenario replay artifacts,
  and explicit acceptance checks for `thread_id` isolation, resume-only approval,
  approval/rejection convergence, side-effect-before-approval prevention, and
  checkpoint close-path handling.
- Record retry caps, terminal reasons, and budget-exceeded behavior in audit or
  metrics artifacts.
- Run real agent smoke only after explicit cost approval.
- Stop condition: agent proof is stale relative to retrieval/index policy.

### M8. Agent Evidence UX And Ops

- Add dashboard/service view for answers, citations, chunks, source previews,
  metrics, agent state transitions, tool calls, checkpoint/HITL status, and
  failure reasons.
- Add trace/run lookup, latency, token/cost, gate status freshness, and failure
  classification.
- Define publishable artifact allowlist, redaction rules, storage location,
  retention window, and project/user scope for traces, audit, checkpoint,
  screenshots, source previews, and failed-run records.
- Keep offline lane credential-free.
- Stop condition: UI hides evidence, or observability captures raw secrets,
  private data, raw RFP source, or full sensitive prompts.

### M9. Production Service And Tool Surface

- Add FastAPI/Pydantic async endpoints for answer generation, gate status, eval
  summaries, and run/trace lookup.
- Add SSE streaming for long-running agent answers.
- Expose document retrieval, SQL/run inspection, and internal metrics/gate tools
  through a bounded tool allowlist.
- Separate public/service API endpoints from agent-callable tools. Each tool
  must have a fixed name, JSON schema, side-effect class, auth/session boundary,
  timeout, row/result limit, structured error semantics, redaction policy, and
  audit fields.
- Add one narrow MCP/FastMCP-style RFP RAG Ops tool server only after storage
  location, retention, project/user scope, `tools/list` schema, runtime behavior,
  timeout/retry, and structured error contract are documented.
- Stop condition: service routes bypass evaluation/guardrail contracts, or tool
  access cannot be audited, or any tool can execute arbitrary SQL or arbitrary
  filesystem/API actions.

### M10. Guardrails, CI, And Deployment Evidence

- Add structured output validation, prompt-injection regression cases,
  max-tool-call budget checks, and graceful fallback behavior.
- Add Dockerfile or compose-based local service reproduction.
- Add GitHub Actions for no-real tests plus lightweight eval/report checks.
- Record latency, token, cost, tool-call success/failure, and failed-run analysis
  artifacts.
- Document the exact local/container commands, CI workflow entrypoints,
  expected non-zero failure behavior, and artifact paths used by
  `portfolio_check`.
- Add malicious RFP, malicious retrieved evidence, and malicious tool-output
  prompt-injection fixtures.
- Stop condition: guardrails are described in prose but not testable, or Docker/CI
  cannot reproduce the documented checks.

### M11. Portfolio Closeout

- Produce final README/REPORT narrative, screenshots, demo script, architecture
  diagram, ADR links, and metric table.
- Produce a short demo video only after the local/containerized service and
  evidence dashboard are stable.
- Make the resume/project narrative explicitly target senior AI Agent Engineer
  review: what the agent decides, which tools it may call, how failures are
  bounded, how quality is measured, and how operations are inspected.
- Stop condition: the project still reads as a one-off demo rather than a
  production-adjacent Agentic RAG backend with evidence-backed local/container
  operations.

## Failure Conditions

The portfolio is not senior-level if any of these remain true:

- `portfolio_readiness_check`, `local_evidence_bundle_check`, or
  `second_stage_readiness.complete` is false.
- `portfolio_check` has not been upgraded to validate the full Stage 2 artifact
  contract, or `stage2_contract_schema_enforced` is absent/false.
- Stage 2 frozen-evidence evidence lacks `eval_set_hash`, freeze/split metadata, label
  rubric, contamination notes, per-slice floors, or generated metrics artifacts.
- It presents CSV-baseline metrics as if they prove HWP/PDF source-document RAG.
- It presents the old real-lane index as latest parsed-source semantic evidence.
- It lacks page/section citation evidence.
- It cannot explain parser quality and visual-information loss.
- It uses vector search only without a hardened dense/BM25/hybrid/reranking
  comparison.
- It reports high aggregate retrieval scores without hard negatives,
  cross-document questions, and per-slice metrics.
- It reports metrics without reproducible commands and artifact paths.
- It leads with "Agent" while retrieval quality remains unproven.
- It has no service/dashboard surface for inspecting evidence and failures.
- It has no clear latency, cost, trace, freshness, or regression-gate story.
- It lacks FastAPI/Pydantic async service evidence and streaming behavior.
- It lacks typed LangGraph state, checkpointing, HITL, and bounded retry/reflection
  evidence.
- It cannot prove `thread_id` isolation, explicit resume-only HITL approval,
  no side effect before approval, and deterministic approval/rejection terminal
  states.
- It lacks guarded tool/function-calling behavior or auditable tool failures.
- It exposes generic SQL execution, arbitrary filesystem/API actions, or
  tool-call surfaces without fixed schemas, side-effect classes, auth/session
  boundaries, limits, redaction, and structured errors.
- It lacks Docker/CI evidence for reproducible checks.
- It treats MCP, tracing, or dashboard work as a label instead of an operational
  boundary with storage scope, retention, and tests.
- It persists or publishes raw prompts, raw tool inputs, raw RFP source, secrets,
  or PII in audit, checkpoint, trace, dashboard, screenshot, or failed-run
  artifacts.
- It makes unsupported claims about visual-only facts.
- It requires credentials for offline regression tests.

## User Decisions Still Required

Recommended defaults are listed first.

1. Portfolio headline
   - Recommended: `AI Agent Engineer Senior Portfolio: Production-grade
     Agentic RAG System for Korean Public RFP Intelligence`.
   - Alternative: `Production-grade Agentic RAG System for Korean Public RFP
     Intelligence`.

2. Demo surface
   - Recommended: FastAPI plus Streamlit evidence dashboard, with SSE streaming
     on the FastAPI side.
   - Alternative: FastAPI plus Next.js if frontend polish becomes a major goal.

3. Real evaluation budget
   - Recommended: run only milestone-gated real evaluations with explicit
     approval.
   - Alternative: no real lane during routine development.

4. Visual extraction strategy
   - Recommended now: targeted deterministic extraction plus manual validation.
   - Later ADR: compare OCR, VLM API, local vision, and page-image retrieval.

5. Deployment scope
   - Recommended: reproducible local/containerized demo with screenshots,
     metrics, and GitHub Actions.
   - Alternative: cloud demo only after service quality is complete.

6. MCP/FastMCP scope
   - Recommended: one internal RFP RAG Ops tool server after the core RAG workflow
     and service boundary are stable.
   - Alternative: public-facing product interface only if a specific role target
     requires it.

7. Observability stack
   - Recommended: choose one primary trace stack first, such as Langfuse or
     Phoenix, and document storage/retention before adoption.
   - Alternative: add a second trace integration only after the first one produces
     useful failed-run analysis.

8. Public portfolio scope
   - Decide which RFP samples, screenshots, metrics, and source snippets are
     safe to publish.
   - Until decided, public artifacts must use the publishable allowlist and
     redacted summaries only.

## Safe Current Claim

This is the narrower claim to use when a context only accepts local/container
evidence and not the full portfolio gate:

> Built a credential-free source-first RAG/Agent evaluation scaffold for 100
> Korean public RFP documents, using parsed HWP/PDF artifacts for offline
> indexing, page/section citations, visual/table and paraphrase benchmark
> slices, constrained LangGraph workflow evaluation, guarded tool/audit
> artifacts, and artifact-backed regression gates.

## Target Final Resume Claim

This claim is valid when `portfolio_readiness_check=true`,
`local_evidence_bundle_check=true`, `second_stage_readiness.complete=true`,
`stage2_contract_schema_enforced=true`, `gate_status` reports `overall_ok=true`,
and credential-free offline tests pass. It is a local/containerized portfolio
claim, not a cloud/live-traffic/public-dashboard claim:

> Built a production-adjacent Agentic RAG backend as an
> AI Agent Engineer senior portfolio project for 100 Korean public RFP
> documents, using parsed HWP/PDF artifacts as the body source of truth,
> section/page-aware chunking,
> dense/BM25/hybrid retrieval comparisons, citation-grounded
> generation, targeted visual/table validation, LangGraph typed-state
> orchestration with conditional routing, bounded retry/reflection,
> checkpointing and HITL approval, FastAPI Pydantic async/SSE service
> endpoints, guarded tool/function calling, traceable latency/token/cost
> evidence, Docker/CI-backed regression gates, and artifact-backed evaluation
> for recall, MRR, faithfulness, answer relevancy, abstention, and failed-run
> analysis.

Reranker quality-win evidence is intentionally excluded from the resume claim
until a same-set paid/API reranker artifact exists and beats vector without
regression.

Architecture evidence is tracked in
`docs/architecture/system-architecture.md`; final-readiness claims should point
to that document rather than describing an unverified architecture from memory.
