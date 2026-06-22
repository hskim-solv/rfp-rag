# Final Portfolio Scorecard

This document explains the deterministic Stage 5 scorecard used to decide
whether the repository is ready to present as a senior AI Agent Engineer
portfolio.

Machine-readable artifact:

```bash
uv run python -m rfp_rag.final_portfolio_scorecard
```

Output:

- `artifacts/final_portfolio_scorecard/summary.json`

## Claim Boundary

The final claim is production-adjacent local/container evidence for a Korean
public RFP Agentic RAG backend. It does not claim hosted cloud production,
live-traffic SLO, provider billing telemetry, full auth/session/rate-limit
operations, or a reranker quality win.

The source of truth for this wording is:

- `docs/portfolio/claim-manifest.json`
- `docs/portfolio/public-package-manifest.json`

## Weighted Rubric

| dimension | weight | gate |
| --- | ---: | --- |
| business problem sharpness | 10 | public docs share the production-adjacent claim and Korean public RFP workload |
| source-first RAG quality | 20 | `stage2_quality_scorecard_complete=true`, quality floor `>= 0.90` |
| agentic engineering depth | 20 | `stage3_agent_scorecard_complete=true`, replay/HITL/trajectory floor `1.0` |
| evaluation rigor | 15 | Stage 2, Stage 3, and fresh-clone offline smoke pass |
| production operations | 15 | `production_readiness`, Stage 4 scorecard, and CI Docker smoke are present |
| guardrails/security | 10 | Stage 4 security floor and public package redaction pass |
| hiring presentation | 10 | README, reviewer pack, company-fit matrix, Korean case study, demo runbook, and resume bullets align |

The final threshold is `score_total >= 90`. A Tier A senior-portfolio claim
should use `score_total=100` and `failed=[]`; `90-99` is acceptable only when
the missing dimension is explicitly named and not central to the target role.

## Fresh Clone Requirement

Fresh clone evidence is generated separately:

```bash
uv run python -m rfp_rag.fresh_clone_smoke
```

The smoke clones the committed HEAD, removes provider credential environment
variables, creates the synthetic CI corpus, and runs `uv sync`, `ruff`, and
`pytest -m "not real"` without `OPENAI_API_KEY`.

## Non-Claims

The scorecard fails closed if public-facing docs assert hosted production,
live-traffic SLOs, provider billing telemetry, reranker quality wins, or
unqualified production-grade claims without the separate evidence and approval
required for those claims.
