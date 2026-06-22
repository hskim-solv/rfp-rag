# Hosted Deployment Runbook

This runbook applies only after the owner approves external deployment. It is
for the public-safe reviewer demo, not for a production SaaS claim.

## Deploy

1. Create a Render Blueprint from `render.yaml`.
2. Set `RFP_RAG_REVIEWER_TOKEN` as a Render secret value.
3. Confirm the service starts on Render's injected `PORT`.
4. Confirm Render health checks use `/healthz`.

## Smoke

```bash
uv run python -m rfp_rag.hosted_demo_smoke \
  --base-url https://<render-service-url> \
  --reviewer-token "$RFP_RAG_REVIEWER_TOKEN" \
  --out artifacts/hosted_demo_smoke/summary.json
```

The smoke must show:

- `hosted_demo_smoke_complete=true`;
- unauthenticated `/v1/answer` returns `401`;
- authenticated `/v1/answer` returns provider `public_demo`;
- SSE returns a `final` event;
- public-safe sources are present;
- no raw RFP text or secrets are emitted.

## Hosted Logs And Metrics Evidence

Create `artifacts/hosted_ops/summary.json` from Render dashboard or Render CLI
observations. Do not paste raw request payloads, raw prompts, secrets, full raw
RFP text, or private user data.

Required fields:

```json
{
  "provider": "render",
  "service_url": "https://<render-service-url>",
  "deployment_status": "live",
  "deploy_smoke_status": "SUCCESS",
  "logs_evidence": {
    "source": "render dashboard or render logs",
    "redacted": true,
    "healthz_2xx_seen": true,
    "answer_2xx_seen": true,
    "unauth_401_seen": true,
    "secret_leak_count": 0,
    "raw_rfp_text_seen": false
  },
  "metrics_evidence": {
    "source": "render service metrics",
    "redacted": true,
    "http_request_count_visible": true,
    "latency_visible": true,
    "error_count_visible": true
  },
  "rollback_evidence": {
    "runbook_path": "docs/portfolio/hosted-deployment-runbook.md",
    "rollback_procedure_documented": true,
    "last_known_good_git_sha": "<deployed git sha>"
  }
}
```

Validate it with:

```bash
uv run python -m rfp_rag.hosted_deployment_evidence \
  --out artifacts/hosted_deployment_evidence/summary.json
```

## Rollback

1. Disable auto-deploy if the deployed revision is bad.
2. In Render, redeploy the last known good commit shown in
   `last_known_good_git_sha`, or revert the bad commit and push.
3. Rotate `RFP_RAG_REVIEWER_TOKEN` if it was exposed during the incident.
4. Rerun `rfp_rag.hosted_demo_smoke`.
5. Rerun `rfp_rag.hosted_deployment_evidence`.
6. Rerun `rfp_rag.final_portfolio_scorecard` and `rfp_rag.portfolio_check`.

## Non-Claims

Passing this runbook proves a public-safe reviewer demo endpoint. It does not
prove multi-tenant auth/session management, provider-backed real RAG quality,
live-traffic SLOs, custom domains, production on-call, or billing telemetry.
