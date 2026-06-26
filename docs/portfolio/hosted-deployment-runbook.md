# Hosted Deployment Runbook

This runbook applies only after the owner approves external deployment. It is
for the public-safe reviewer demo, not for a production SaaS claim.

## Deploy

Before external deployment, run the same public-safe hosted profile locally:

```bash
./scripts/local-hosted-demo-smoke.sh
```

This starts the FastAPI service with `RFP_RAG_PUBLIC_DEMO_MODE=1`, reviewer-token
auth, rate limiting, and `RFP_RAG_GIT_SHA`, then runs the hosted smoke against
`http://127.0.0.1:8017`.

## Hugging Face Space Deploy

When Render dashboard/API access is unavailable, deploy the same public-safe
Docker service to a free Hugging Face Space:

```bash
RFP_RAG_REVIEWER_TOKEN="$(openssl rand -hex 32)" \
DEPLOYED_GIT_SHA="$(git rev-parse --short HEAD)" \
./scripts/deploy-hf-space.sh
```

The script creates or updates `hskim-solv/rfp-rag-reviewer-demo`, uploads the
Docker Space bundle, sets public demo variables, and stores the reviewer token
as a Space secret. The expected HTTPS URL is:

```text
https://hskim-solv-rfp-rag-reviewer-demo.hf.space
```

Then run `./scripts/hosted-evidence.sh` with
`HOSTED_PROVIDER=huggingface_spaces`.

## localhost.run HTTPS Tunnel Deploy

When dashboard/API hosted providers are unavailable, the current public-safe
reviewer evidence may be generated through an anonymous `localhost.run` HTTPS
tunnel. This is not an always-on hosted production claim.

1. Start the local public-safe hosted profile with `RFP_RAG_PUBLIC_DEMO_MODE=1`,
   `RFP_RAG_REVIEWER_TOKEN`, `RFP_RAG_RATE_LIMIT_PER_MINUTE=20`, and
   `RFP_RAG_GIT_SHA`.
2. Open an SSH reverse tunnel:

```bash
ssh -F /dev/null -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  -R 80:localhost:8017 nokey@localhost.run
```

3. Run the evidence script with `HOSTED_PROVIDER=localhost_run_tunnel`.

## Render Blueprint Deploy

1. Create a Render Blueprint from `render.yaml`.
2. Set `RFP_RAG_REVIEWER_TOKEN` as a Render secret value.
3. Set `RFP_RAG_GIT_SHA` to the deployed commit SHA, for example
   `git rev-parse --short HEAD`.
4. Confirm the service starts on Render's injected `PORT`.
5. Confirm Render health checks use `/healthz`.

## Smoke

```bash
uv run python -m rfp_rag.hosted_demo_smoke \
  --base-url https://<render-service-url> \
  --reviewer-token "$RFP_RAG_REVIEWER_TOKEN" \
  --expected-git-sha "$(git rev-parse --short HEAD)" \
  --rate-limit-probe-count 25 \
  --out artifacts/hosted_demo_smoke/summary.json
```

The smoke must show:

- `hosted_demo_smoke_complete=true`;
- unauthenticated `/v1/answer` returns `401`;
- authenticated `/v1/answer` returns provider `public_demo`;
- repeated authenticated probes observe `429 rate_limited`;
- SSE returns a `final` event;
- public-safe sources are present;
- `/healthz` reports the expected `RFP_RAG_GIT_SHA`;
- no raw RFP text or secrets are emitted.

## Hosted Logs And Metrics Evidence

Create `artifacts/hosted_ops/summary.json` from Render dashboard or Render CLI
observations. Do not paste raw request payloads, raw prompts, secrets, full raw
RFP text, or private user data.

After the hosted URL is approved, the reviewer token is configured, and the
operator has checked logs, metrics, and rollback evidence, run the full evidence
chain with:

```bash
SERVICE_URL=https://<render-service-url> \
RFP_RAG_REVIEWER_TOKEN="$RFP_RAG_REVIEWER_TOKEN" \
DEPLOYED_GIT_SHA="$(git rev-parse --short HEAD)" \
CONFIRM_LOGS_REDACTED=true \
CONFIRM_METRICS_VISIBLE=true \
CONFIRM_ROLLBACK_RUNBOOK=true \
./scripts/hosted-evidence.sh
```

The script fails closed unless `SERVICE_URL` is HTTPS and all three confirmation
variables are explicitly `true`.

Use the helper after confirming the required observations in Render:

```bash
uv run python -m rfp_rag.hosted_ops_summary \
  --service-url https://<render-service-url> \
  --deployed-git-sha "$(git rev-parse --short HEAD)" \
  --out artifacts/hosted_ops/summary.json \
  --confirm-logs-redacted \
  --confirm-metrics-visible \
  --confirm-rollback-runbook
```

The confirmation flags mean the operator has checked the hosted provider
surface, not merely run the local helper:

- `--confirm-logs-redacted`: hosted logs or provider log view show health,
  authenticated answer, and unauthenticated `401` activity without secrets, raw
  prompts, raw RFP text, or private payloads;
- `--confirm-metrics-visible`: hosted service metrics expose request/error and
  latency visibility sufficient for reviewer evidence;
- `--confirm-rollback-runbook`: rollback evidence points to this runbook and the
  deployed git SHA.

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

## GitHub Actions Evidence

After adding repository secret `RFP_RAG_REVIEWER_TOKEN`, run
`.github/workflows/hosted-demo-smoke.yml` manually with the approved HTTPS
`service_url` and set all three confirmation inputs to true only after checking
the hosted logs, metrics, and rollback evidence. The workflow does not accept
the reviewer token as an input; it uses the repository secret and uploads:

- `artifacts/hosted_demo_smoke/summary.json`;
- `artifacts/hosted_ops/summary.json`;
- `artifacts/hosted_deployment_evidence/summary.json`;
- `artifacts/production_readiness/summary.json`;
- `artifacts/final_portfolio_scorecard/summary.json`;
- `artifacts/portfolio_readiness.json`.

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
