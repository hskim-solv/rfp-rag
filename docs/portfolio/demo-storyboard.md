# 3-Minute Reviewer Demo Storyboard

Target reviewer: Korean senior AI agent engineer interviewer.

## 0:00-0:30 Problem and System Boundary

- State the product problem: Korean public RFP documents are complex,
  table-heavy, and citation-sensitive.
- State the non-claim: this is local/container production-adjacent evidence, not
  a public hosted service.

## 0:30-1:20 One-Command Demo

- Run `uv run python -m rfp_rag.top_tier_demo`.
- Show health, answer, SSE streaming, gates, and ops summary checks.
- Point to generated artifact `artifacts/top_tier_demo/summary.json`.

## 1:20-2:10 Evaluation and Agent Evidence

- Show Stage 3 holdout metrics, eval set hash, and failure-closed finalizer.
- Show LangGraph planner-executor evidence, HITL/checkpoint behavior, and audit
  redaction.

## 2:10-2:45 Observability and Security

- Show redacted traces, failed-run analysis, latency/cost/tool summaries.
- Show prompt-injection, secrets/PII, tool allowlist, and budget-limit evidence.

## 2:45-3:00 Senior Defense

- Explain why vector retrieval remains until a measured reranker win exists.
- Explain hosted deployment, auth, rate limit, and live SLOs as explicit future
  production decisions, not hidden claims.
