# Stage 4 Operations And Risk Scorecard

Date: 2026-06-22

This document explains the deterministic Stage 4 operations and risk scorecard
used by the senior portfolio roadmap. The machine-readable artifact is
generated with:

```bash
uv run python -m rfp_rag.stage4_ops_risk_scorecard
```

Output:

- `artifacts/stage4_ops_risk_scorecard/summary.json`

## Purpose

The scorecard makes the operating story reviewable in one place. It aggregates:

- redacted trace and failed-run evidence from `artifacts/observability/summary.json`
- local service smoke and latency/token-cost evidence from `artifacts/service_ops/summary.json`
- prompt-injection, malicious evidence/tool, redaction, retention, and leak
  checks from `artifacts/security_redteam/summary.json`
- reliability and deterministic replay evidence from
  `artifacts/reliability_security/summary.json`
- token/cost budget coverage from `artifacts/cost_budget/summary.json`
- dependency security evidence from `artifacts/security_alerts/summary.json`
- deployment boundary evidence from `artifacts/deployment_readiness/summary.json`

## Acceptance Thresholds

| area | required signal |
| --- | --- |
| Observability | trace export present, latency p50/p95 recorded, token/cost recorded, tool success recorded, at least 5 failed-run analyses |
| Service ops | health, answer, stream, gates, ops summary, path safety, token/cost distribution all pass |
| Security red team | prompt-injection/malicious document/malicious evidence/malicious tool checks pass, no secret/PII leak, no raw persistence, no tool policy violation |
| Reliability | at least 20 red-team cases, prompt-injection block recall 1.0, fallback recovery, deterministic replay |
| Cost budget | token and cost record coverage 1.0, budget violations 0 |
| Dependency security | patched/absent vulnerable dependencies and unresolved unaccepted alerts 0 |
| Deployment boundary | public exposure requires approval, rate-limit and secret handling documented, SSE error event contract present |

## Important Non-claim

This is reviewer-demo operations evidence. It does not claim full hosted
production SaaS, live-traffic SLO, incident history, or provider billing
telemetry.

Latency values are preserved as local measured evidence. They are not presented
as production SLOs until live traffic, monitoring windows, incident response
scope, and SLO targets are explicitly approved.
