# 2026 RFP RAG Final Goal

## Final Positioning

Target portfolio headline:

> Production-grade Agentic RAG System for Korean Public RFP Intelligence.

The project should not be presented as an RFP chatbot. The final story is:

> A production-grade Agentic RAG backend using Korean public procurement RFPs as
> the concrete workload: source-first HWP/PDF ingestion, evaluated retrieval,
> LangGraph orchestration, tool-using workflows, streaming FastAPI service,
> observability, guardrails, and CI-backed evaluation gates.

This positioning is stronger for Korean 2026 hiring signals than a narrow
"Retrieval & Evaluation Engineer" headline. Korean postings usually use broader
titles such as `LLM/RAG AI Engineer`, `AI Agent Backend Engineer`, `RAG Engine
Researcher`, or `RAG & Graph Search Engineer`, while still screening for the
same hard capabilities: Python backend engineering, document parsing, chunking,
vector/hybrid retrieval, reranking, citation grounding, evaluation, typed agent
state, API/service operation, observability, latency, cost control, deployment,
and guardrails.

This document describes the final target, not the current public claim. Current
safe claims and missing senior-ready evidence are separated below.

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

As of 2026-06-17, the portfolio is **senior-promising-but-not-yet**. It should
not be described as senior-ready until the blocker items below are closed.

Current safe evidence:

- Source-first offline index and evaluation use parsed artifacts:
  `artifacts/index/manifest.json` records `text_source=parsed`,
  `parse_manifest_path=artifacts/parsed_docs/manifest.jsonl`, and
  `chunk_count=16459`.
- The latest source-first real lane uses `artifacts/index_real` with
  `text_source=parsed`, `parse_manifest_path=artifacts/parsed_docs/manifest.jsonl`,
  contract `rfp-rag-real-v5`, and a 545-query `artifacts/eval_real` run with
  `rag_quality_complete=true`.
- The LLM reranker path is an implemented interface with artifact fields and
  credential-free offline guards; no real/open reranker quality claim exists yet.
- The visual lane has a precision-hardened local OCR candidate, reviewed
  page-level visual evidence, and a 25-question `visual_table` offline eval slice
  with `visual_evidence_hit_rate=0.92`; this is still not production visual
  understanding.
- The agent lane proves constrained offline workflow routing, verification,
  audit, checkpoint, and HITL behavior against the current offline retrieval
  policy. Optional real smoke still requires explicit cost approval.
- The FastAPI service slice exposes `/healthz`, `/v1/answer`,
  `/v1/answer/stream`, and `/v1/gates` as a thin typed API over existing RAG and
  gate evidence. It is not yet a deployed service or dashboard.

Current unsafe claims:

- "Hybrid or reranking improved retrieval quality."
- "Artifact-backed latency and cost gates are complete."
- "Production visual understanding or multimodal RAG is solved."
- "The repository is senior-ready as a service/dashboard portfolio."

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
     audit, or evaluation artifacts.
   - Include an internal ops/API tool for gate status, metrics, or artifact
     comparison.
   - Include one narrow MCP/FastMCP-style tool server for RFP RAG Ops after the
     tool boundary, storage scope, and retention policy are explicit.

## Quality Targets

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
- Current offline set: 545 total queries after the paraphrase slice, including
  400 metadata, 30 hard abstention, 30 section lookup, 20 cross-document, 25
  reviewed visual/table, and 30 paraphrase questions.
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

Generation targets:

- Citation presence: 100%.
- Faithfulness: >= 0.95.
- Answer relevancy: >= 0.88.
- Unsupported/no-answer abstention pass rate: >= 0.90.

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
- Current agent lane must be rerun with the current index/min-score policy before
  it is cited as latest-stack evidence.
- Real LLM router/rewriter smoke is optional but must be explicitly approved
  because it is cost-bearing.
- LangGraph graph uses typed state schema, conditional edges, checkpointing, and
  bounded retry/reflection loops.
- Final workflow includes a planner-executor or supervisor-worker split only if
  it maps to real RFP work such as compare, verify, draft report, and approve.

Ops/service targets:

- Offline lane remains credential-free:
  `python3 -m pytest -m "not real"` must pass without `OPENAI_API_KEY`.
- Real lane is run only on explicit approval because it costs money.
- FastAPI service exposes Pydantic schemas, async handlers, and SSE streaming.
- Structured output validation is enforced on agent/tool-facing responses.
- Tool allowlist, max tool-call budget, prompt-injection checks, and
  secrets/PII leakage safeguards are covered by tests or scripted checks.
- Dashboard or report shows gate freshness, latency, token/cost estimate, and
  failure classification.
- Containerized or local service demo can be reproduced from documented
  commands.
- Docker build and GitHub Actions CI are documented and run the no-real tests
  plus lightweight eval/report checks.
- Token/cost estimate coverage: 100% of generated evaluation predictions where
  a real/open model is used.
- Latency reporting coverage: 100% of service/demo requests and evaluation
  predictions. Do not publish a latency threshold claim until the measured
  baseline is recorded.

## Milestones

### M0. Baseline Lock

- Confirm current dirty worktree scope.
- Run credential-free test gate.
- Confirm report check and current metrics.
- Stop condition: unrelated user edits block safe documentation or tests.

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
  cross-document questions, and section/table/visual slices. Current gap:
  paraphrases and the last 5 reviewed visual/table questions needed for the
  30-question visual/table target.
- Report per-slice metrics and failure examples.
- Stop condition: high aggregate scores can be explained by an easy or narrow
  query set.

### M5. Retrieval And Reranker Ablation

- Compare dense, BM25, hybrid RRF, and reranked retrieval.
- Report quality, latency, and cost trade-offs.
- Stop condition: quality gains are not statistically or operationally
  defensible.

### M6. Source-First Real Quality Gate

- Run approved real-lane evaluation on the parsed-source index.
- Update `REPORT.md` from generated artifacts, not by hand-editing metrics.
- Stop condition: real-lane cost approval is missing, or the real index manifest
  lacks parsed-source lineage.

### M7. Agent Freshness

- Rerun offline agent evaluation with the current retrieval policy.
- Add trajectory/audit/checkpoint examples to the evidence surface.
- Run real agent smoke only after explicit cost approval.
- Stop condition: agent proof is stale relative to retrieval/index policy.

### M8. Evidence UX And Ops

- Add dashboard/service view for answers, citations, chunks, source previews,
  metrics, and failure reasons.
- Add trace, latency, token/cost, gate status freshness, and failure
  classification.
- Keep offline lane credential-free.
- Stop condition: UI hides evidence, or observability captures raw secrets,
  private data, raw RFP source, or full sensitive prompts.

### M9. Production Service And Tool Surface

- Add FastAPI/Pydantic async endpoints for answer generation, gate status, eval
  summaries, and run/trace lookup.
- Add SSE streaming for long-running agent answers.
- Expose document retrieval, SQL/run inspection, and internal metrics/gate tools
  through a bounded tool allowlist.
- Add one narrow MCP/FastMCP-style RFP RAG Ops tool server only after storage
  location, retention, and project/user scope are documented.
- Stop condition: service routes bypass evaluation/guardrail contracts, or tool
  access cannot be audited.

### M10. Guardrails, CI, And Deployment Evidence

- Add structured output validation, prompt-injection regression cases,
  max-tool-call budget checks, and graceful fallback behavior.
- Add Dockerfile or compose-based local service reproduction.
- Add GitHub Actions for no-real tests plus lightweight eval/report checks.
- Record latency, token, cost, tool-call success/failure, and failed-run analysis
  artifacts.
- Stop condition: guardrails are described in prose but not testable, or Docker/CI
  cannot reproduce the documented checks.

### M11. Portfolio Closeout

- Produce final README/REPORT narrative, screenshots, demo script, architecture
  diagram, ADR links, and metric table.
- Produce a short demo video only after the local/containerized service and
  evidence dashboard are stable.
- Stop condition: the project still reads as a demo rather than a production-grade
  Agentic RAG system with evidence-backed operations.

## Failure Conditions

The portfolio is not senior-level if any of these remain true:

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
- It lacks guarded tool/function-calling behavior or auditable tool failures.
- It lacks Docker/CI evidence for reproducible checks.
- It treats MCP, tracing, or dashboard work as a label instead of an operational
  boundary with storage scope, retention, and tests.
- It makes unsupported claims about visual-only facts.
- It requires credentials for offline regression tests.

## User Decisions Still Required

Recommended defaults are listed first.

1. Portfolio headline
   - Recommended: `Production-grade Agentic RAG System for Korean Public RFP
     Intelligence`.
   - Alternative: `LLM/RAG AI Engineer - source-first RAG and agent backend`.

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

## Safe Current Claim

This is the claim that can be used before the remaining senior-ready gates are
closed:

> Built a credential-free source-first RAG/Agent evaluation scaffold for 100
> Korean public RFP documents, using parsed HWP/PDF artifacts for offline
> indexing, page/section citations, visual/table and paraphrase benchmark slices,
> constrained LangGraph workflow evaluation, and artifact-backed regression
> gates.

## Target Final Resume Claim

This claim is valid only after benchmark hardening, source-first real gate,
reranker ablation, production service, guardrails, evidence UX, and ops metrics
pass:

> Built a production-grade Agentic RAG system for 100 Korean public RFP
> documents, using parsed HWP/PDF artifacts as the body source of truth,
> section/page-aware chunking, dense/BM25/hybrid/reranked retrieval comparisons,
> citation-grounded generation, targeted visual/table validation, LangGraph
> typed-state orchestration with checkpointing and HITL approval, FastAPI
> Pydantic async/SSE service endpoints, guarded tool/function calling, traceable
> latency/token/cost evidence, Docker/CI-backed regression gates, and
> artifact-backed evaluation for recall, MRR, faithfulness, answer relevancy,
> abstention, and failed-run analysis.
