# RFP Agentic RAG Case Study

## Problem

Korean public RFP review is a complex-document workflow, not a simple chatbot
problem. A reviewer needs to inspect HWP/PDF source documents, compare
requirements across notices, trust citations, detect missing support, and make
go/no-go decisions under deadline pressure. CSV metadata alone is insufficient:
the body source of truth must come from parsed source artifacts with document,
section, page, and chunk lineage.

The portfolio problem is therefore:

> Build a production-adjacent Agentic RAG system that can answer and route RFP
> questions with evidence, abstain when unsupported, expose service and tool
> behavior, and prove quality through repeatable gates.

## Architecture decisions

The system keeps the workload narrow and hard: 100 Korean public RFP HWP/PDF
documents. The CSV is metadata registry only. Parsed artifacts feed chunking,
indexing, retrieval, generation, and evaluation.

Key decisions:

- Source-first ingestion: prevent the project from becoming CSV search dressed
  as RAG.
- Qdrant/vector baseline: keep the strongest measured retrieval path until BM25,
  hybrid, or reranking beats it on the same frozen set without regressions.
- LangGraph workflow: route, retrieve, grade, rewrite, generate, verify, and
  HITL approval are typed and replayable instead of hidden in prompt text.
- FastAPI/Pydantic/SSE surface: prove backend integration shape, not only CLI
  scripts.
- Gate-first evidence: `gate_status`, `portfolio_check`, and CI fail stale or
  shallow artifacts closed.
- Production-adjacent wording: claim local/container evidence honestly; do not
  claim hosted production, live-traffic SLOs, or multi-tenant readiness without
  deployment evidence.

## Evaluation evidence

The project uses layered evidence rather than one vanity score:

- offline regression: credential-free corpus/index/RAG plumbing;
- real RAG lane: parsed-source semantic quality with model and prompt lineage;
- Stage 2 frozen evidence: query coverage, real metrics, agent stress,
  retrieval bakeoff, visual quality, service ops, deterministic security smoke,
  and cost budget;
- top-tier evidence: one-command reviewer demo, Stage 3 independent holdout,
  real observability, upgraded orchestration, security/reliability deepening,
  production-facing readiness artifacts, dependency security hygiene, and this
  case study are checked separately from hosted-production claims.

Representative current checks:

- `uv run python -m rfp_rag.gate_status`;
- `uv run python -m rfp_rag.portfolio_check --out artifacts/portfolio_readiness.json`;
- `uv run python -m rfp_rag.production_readiness`;
- `uv run python -m rfp_rag.top_tier_demo`;
- `uv run python -m pytest -m "not real" -q`.

## Failure analysis

The most important failures found during hardening were not model failures. They
were portfolio-evidence failures:

- overclaiming production readiness without hosted production evidence;
- treating a frozen evidence set like an independent public-traffic holdout;
- shallow boolean artifacts that could pass without metrics, thresholds, or
  lineage;
- unsafe demo artifacts that might expose raw prompts, raw RFP text, or secrets;
- unresolved dependency alerts that would weaken the public portfolio signal;
- tool/server payloads that accepted unknown or malformed arguments;
- agent claims that were broader than the measured checkpoint, HITL, and audit
  evidence.

The current system responds by making those failure modes machine-visible:
contracts include required fields, thresholds, source hashes, split manifests,
redaction scans, and explicit non-claims.

## Operational boundaries

What is proven:

- local/container reviewer demo path;
- independent Stage 3 holdout quality: `document_count=20`, `query_count=100`,
  `recall@5=1.0`, `mrr=1.0`, `citation_validity=1.0`,
  `faithfulness=0.9887`, `answer_relevancy=0.8797`,
  `unsupported_visual_claim_rate=0.0`, `abstention_precision=1.0`;
- typed API and SSE service surface;
- LangGraph replay evidence for routing, rewriting, abstention, HITL, checkpoint
  closure, and audit redaction;
- deterministic security smoke and artifact redaction scan;
- production-facing reviewer package: 3-minute demo storyboard, generated
  evidence artifacts, hosted-deployment readiness plan, auth/rate-limit and
  secret-handling boundaries, and dependency security register;
- dependency security hygiene: vulnerable `ragas` judge dependency removed by
  ADR-0021, `diskcache` absent, `langchain` locked above the patched floor, and
  GitHub Dependabot open alert count `0`;
- cost/token estimates from persisted prediction artifacts;
- CI-backed credential-free regression and Docker build.

What is not claimed yet:

- hosted cloud production;
- public multi-tenant dashboard;
- live-traffic SLOs;
- provider billing telemetry;
- reranker quality win.

## Interview defense

**Why is this senior-level rather than another RAG demo?**

Because the main artifact is not a single answer. It is an evaluated,
contract-checked system: source parsing, retrieval, generation, agent workflow,
service API, security, observability, cost, and CI all produce inspectable
evidence.

**Why keep vector retrieval when hybrid/reranker sounds more advanced?**

Because senior engineering should choose measured wins, not fashionable
components. ADR-0020 keeps vector until another mode wins on the same set
without recall, citation, abstention, visual-evidence, latency, or cost
regressions.

**Why not claim production-grade?**

Because production-grade requires hosted deployment, auth, rate limits,
monitoring, incident/failure evidence, and live-operational boundaries. This repo
proves production-adjacent engineering evidence and hosted-deployment readiness
without claiming public traffic.

**What would you build next?**

Hosted deployment is next: auth, rate limits, public dashboard or trace export,
provider billing telemetry, and live-traffic SLOs. The repo already keeps those
separate from the local top-tier portfolio evidence.
