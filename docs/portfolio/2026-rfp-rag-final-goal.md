# 2026 RFP RAG Final Goal

## Final Positioning

Target portfolio headline:

> LLM/RAG AI Engineer for complex-document parsing, retrieval evaluation, and
> evidence-grounded RAG/Agent backends.

The project should not be presented as an RFP chatbot. The final story is:

> A source-first RAG quality-engineering system for Korean public procurement
> RFPs, built from original HWP/PDF documents, with parser fidelity checks,
> section/page-grounded retrieval, hybrid retrieval and reranking experiments,
> agentic verification, and operator-facing quality evidence.

This positioning is stronger for Korean 2026 hiring signals than a narrow
"Retrieval & Evaluation Engineer" headline. Korean postings usually use broader
titles such as `LLM/RAG AI Engineer`, `AI Agent Backend Engineer`, `RAG Engine
Researcher`, or `RAG & Graph Search Engineer`, while still screening for the
same hard capabilities: document parsing, chunking, vector/hybrid retrieval,
reranking, citation grounding, evaluation, API/service operation, observability,
latency, and cost control.

## Scope Boundaries

In scope:

- 100 original Korean public RFP HWP/PDF documents as the body source of truth.
- CSV only as a metadata registry for project name, agency, budget, deadline,
  and filename.
- Parsed artifacts, page/section citations, visual-structure evidence, and
  reproducible evaluation artifacts.
- Offline credential-free tests and real-lane quality gates as separate lanes.
- LangGraph-style workflow only where it improves routing, retrieval,
  verification, abstention, audit, or human approval.
- A small service or dashboard surface that exposes evidence, metrics, and
  traceable runs.

Out of scope for the final portfolio core:

- Claiming CSV-baseline retrieval as source-document quality.
- Presenting a generic chatbot UI as the main achievement.
- Full autonomous multi-agent behavior without measurable retrieval gains.
- FastMCP/MCP as the main product story before the RAG workflow is stable.
- Cloud production deployment unless local/containerized evidence is already
  complete.

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

## Quality Targets

Parser/source targets:

- `doc_count`: 100 source RFPs.
- Empty parsed text documents: 0.
- Average parser quality score: >= 0.95.
- Low-quality parsed documents: 0, unless each has a documented exception.
- Page citation availability: 100%.
- CSV body fallback for RAG content: 0.

Retrieval targets:

- Real-lane `Recall@5`: >= 0.95.
- Real-lane `Recall@3`: >= 0.90.
- Real-lane `MRR`: >= 0.85.
- Section hit rate: >= 0.90 on section-labeled questions.
- Metadata exact match: >= 0.95.

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

Agent/workflow targets:

- Query route, retrieve, rewrite, generate, verify, abstain, audit, checkpoint,
  and HITL resume paths covered by tests or scripted demos.
- Agent lane gate passes with artifact-backed metrics.
- Tool calls and state transitions are inspectable from audit artifacts.

Ops/service targets:

- Offline lane remains credential-free:
  `python3 -m pytest -m "not real"` must pass without `OPENAI_API_KEY`.
- Real lane is run only on explicit approval because it costs money.
- Dashboard or report shows gate freshness, latency, token/cost estimate, and
  failure classification.
- Containerized or local service demo can be reproduced from documented
  commands.

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

### M3. Visual MVP

- Turn manual visual audit into targeted visual-structure extraction.
- Cover schedules, organization charts, architecture diagrams, screenshots, and
  tables where text extraction loses business meaning.
- Stop condition: visual claims cannot be tied back to page evidence.

### M4. Retrieval Ablation

- Compare dense, BM25, hybrid RRF, and reranked retrieval.
- Report quality, latency, and cost trade-offs.
- Stop condition: quality gains are not statistically or operationally
  defensible.

### M5. Real Quality Gate

- Run approved real-lane evaluation.
- Update `REPORT.md` from generated artifacts, not by hand-editing metrics.
- Stop condition: real-lane cost approval is missing.

### M6. Evidence UX

- Add dashboard/service view for answers, citations, chunks, source previews,
  metrics, and failure reasons.
- Stop condition: UI hides evidence instead of making quality inspectable.

### M7. Ops Evidence

- Add trace, latency, token/cost, gate status, and failure classification.
- Keep offline lane credential-free.
- Stop condition: observability captures raw secrets, private data, or full
  sensitive prompts.

### M8. Portfolio Closeout

- Produce final README/REPORT narrative, screenshots, demo script, architecture
  diagram, ADR links, and metric table.
- Stop condition: the project still reads as a demo rather than an evidence-led
  engineering system.

## Failure Conditions

The portfolio is not senior-level if any of these remain true:

- It presents CSV-baseline metrics as if they prove HWP/PDF source-document RAG.
- It lacks page/section citation evidence.
- It cannot explain parser quality and visual-information loss.
- It uses vector search only without a hybrid/reranking comparison.
- It reports metrics without reproducible commands and artifact paths.
- It leads with "Agent" while retrieval quality remains unproven.
- It has no service/dashboard surface for inspecting evidence and failures.
- It has no clear latency, cost, trace, or regression-gate story.
- It makes unsupported claims about visual-only facts.
- It requires credentials for offline regression tests.

## User Decisions Still Required

Recommended defaults are listed first.

1. Portfolio headline
   - Recommended: `LLM/RAG AI Engineer`.
   - Alternative: `Retrieval & Evaluation Engineer` for global specialist
     roles.

2. Demo surface
   - Recommended: FastAPI plus Streamlit evidence dashboard.
   - Alternative: FastAPI plus Next.js if frontend polish becomes a major goal.

3. Real evaluation budget
   - Recommended: run only milestone-gated real evaluations with explicit
     approval.
   - Alternative: no real lane during routine development.

4. Visual extraction strategy
   - Recommended now: targeted deterministic extraction plus manual validation.
   - Later ADR: compare OCR, VLM API, local vision, and page-image retrieval.

5. Deployment scope
   - Recommended: reproducible local/containerized demo with screenshots and
     metrics.
   - Alternative: cloud demo only after service quality is complete.

6. MCP/FastMCP scope
   - Recommended: internal operator/tooling layer after the core RAG workflow is
     stable.
   - Alternative: public-facing product interface only if a specific role target
     requires it.

7. Public portfolio scope
   - Decide which RFP samples, screenshots, metrics, and source snippets are
     safe to publish.

## Final Resume Claim

> Built a source-first RAG quality system for 100 Korean public RFP documents,
> using parsed HWP/PDF artifacts as the body source of truth, section/page-aware
> chunking, hybrid retrieval and reranking, citation-grounded generation,
> targeted visual-structure validation, LangGraph-style verification workflow,
> and artifact-backed gates for recall, MRR, faithfulness, answer relevancy,
> abstention, latency, and cost.
