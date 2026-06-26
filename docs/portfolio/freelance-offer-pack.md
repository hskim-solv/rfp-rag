# Freelance Offer Pack

This pack translates the RFP Agentic RAG system into paid project shapes. It is written for clients who need document search, question answering, or workflow automation over private business documents.

## Best-Fit Client Problems

- Internal document QA over PDFs, HWP, policies, manuals, contracts, proposals, or RFPs.
- Procurement or proposal teams that repeatedly inspect long public notices.
- Teams that need cited answers and abstention rather than generic chatbot replies.
- Teams that need a deployable backend, not a notebook.

## Offer 1: Document RAG Diagnostic

**Delivery window:** 1-2 weeks.

**Client inputs:**

- 20-50 representative documents.
- 20-40 real questions.
- One owner who can label answer usefulness.

**Deliverables:**

- Ingestion and parsing quality report.
- Retrieval baseline with recall and citation checks.
- Failure taxonomy.
- Recommendation: continue, redesign corpus, or stop.

**Acceptance tests:**

```bash
uv run python -m rfp_rag.business_readiness --out artifacts/business_readiness/summary.json
uv run python -m rfp_rag.portfolio_check --out artifacts/portfolio_check/summary.json
```

The client version should replace public RFP data with client-approved data and keep raw client content out of public artifacts.

## Offer 2: Internal RAG MVP

**Delivery window:** 3-6 weeks.

**Client inputs:**

- 100-1,000 documents.
- Access policy for who can query which documents.
- Deployment target: local server, cloud VM, or managed container.

**Deliverables:**

- FastAPI backend.
- Document ingestion job.
- Retrieval and answer endpoint.
- Citation-bearing answers.
- Basic auth boundary.
- Smoke tests and runbook.

**Acceptance tests:**

- `/healthz` returns 200.
- Answer endpoint returns citations for answerable questions.
- Unsupported questions abstain.
- Prompt injection fixtures do not override system rules.
- Fresh clone or clean deploy smoke passes.

## Offer 3: Agentic Workflow Automation

**Delivery window:** 6-10 weeks.

**Client inputs:**

- A repeated workflow with clear steps and owner approvals.
- Tool/API access boundaries.
- A list of actions requiring human approval.

**Deliverables:**

- LangGraph workflow with typed state.
- Tool allowlist.
- Checkpoint and replay path.
- Human approval node.
- Failure analysis report.

**Acceptance tests:**

- Tool budget is enforced.
- Human approval is required for write/export actions.
- Failed runs are traceable.
- Retry/rewrite behavior is visible in logs or artifacts.

## Pricing Guidance

These are positioning bands, not quotes:

| Package | Suggested band | Why |
| --- | ---: | --- |
| Document RAG Diagnostic | KRW 3M-8M | Bounded analysis with clear stop/go output. |
| Internal RAG MVP | KRW 12M-35M | Backend, ingestion, evaluation, deployment, and runbook. |
| Agentic Workflow Automation | KRW 30M-80M | Workflow design, tool contracts, HITL, evaluation, and operational hardening. |

## Scope Boundaries

- No unbounded data cleanup.
- No unsupported cloud bill responsibility.
- No customer production secret stored in this public repo.
- No model training, RLHF, or fine-tuning unless separately scoped.
- No legal, medical, or financial advice claims from generated answers.

## Proof From This Repo

- `docs/portfolio/case-study.md`
- `docs/portfolio/senior-reviewer-pack.md`
- `artifacts/hosted_demo_smoke/summary.json`
- `artifacts/final_portfolio_scorecard/summary.json`
- `scripts/reviewer-10m.sh`
