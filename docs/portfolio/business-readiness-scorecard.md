# Business Readiness Scorecard

This document separates three different questions that are easy to mix up:

1. Can this project help win senior AI Agent/RAG interviews?
2. Can this project support paid freelance proposals?
3. Can this project become a startup product?

## Current Answer

| Outcome | Status | Reason |
| --- | --- | --- |
| Senior AI Agent/RAG employment | Ready to lead with | The repo has source-first RAG, LangGraph agent workflow, FastAPI service, Docker/CI, hosted reviewer demo evidence, scorecards, guardrails, and fresh clone smoke. |
| Freelance RAG/document-AI work | Ready for scoped discovery and small/medium projects | The repo proves delivery ability, but needs each client scope constrained by data access, deployment target, support window, and acceptance tests. |
| Startup SaaS | Ready for customer discovery, not full SaaS sales | The repo proves technical feasibility, but not recurring user demand, onboarding UX, multi-tenant operations, billing, support, or live SLOs. |

## Machine Check

Run:

```bash
uv run python -m rfp_rag.business_readiness --out artifacts/business_readiness/summary.json
```

Expected readiness thresholds:

| Score | Threshold | Meaning |
| --- | ---: | --- |
| employment | 90 | Strong enough to lead senior AI Agent/RAG applications. |
| freelance | 80 | Strong enough to use in paid project discovery and proposals. |
| startup_discovery | 65 | Strong enough to interview customers and test willingness to pay. |

## Non-Claims

- This is not yet full hosted SaaS.
- This does not prove product-market fit.
- This does not prove live customer revenue.
- This does not prove multi-tenant security review.
- This does not prove paid cloud SLO.

## Evidence Map

| Claim | Evidence |
| --- | --- |
| Strong senior hiring signal | `docs/portfolio/case-study.md`, `docs/portfolio/company-fit-matrix.md`, `artifacts/final_portfolio_scorecard/summary.json` |
| Reviewer can inspect a public-safe demo | `artifacts/hosted_demo_smoke/summary.json`, `docs/portfolio/senior-reviewer-pack.md` |
| Client delivery process can be scoped | `docs/portfolio/freelance-offer-pack.md`, `docs/portfolio/demo-runbook.md` |
| Startup discovery can begin honestly | `docs/portfolio/startup-validation-plan.md` |
