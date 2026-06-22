# ADR-0022: Public-Safe Hosted Reviewer Demo Platform

## Status

Proposed default, pending owner approval before external deployment.

## Context

The portfolio is moving from `production_adjacent_local_container_evidence` to a
bounded `public_safe_hosted_reviewer_demo` claim. The hosted demo must expose the
FastAPI service over HTTPS without publishing raw RFP text, provider credentials,
or paid real-provider lanes. The first hosted phase is a reviewer demo, not a
live-traffic SaaS production claim.

## Decision Criteria

| Criterion | Weight | Why it matters |
|---|---:|---|
| Cost/spend risk | 30 | The first phase must be cost-free or tightly bounded. |
| Docker/FastAPI fit | 20 | The repo already has a Dockerized FastAPI service. |
| HTTPS reviewer URL | 15 | Reviewers need a simple public URL. |
| Env/secrets support | 15 | Demo mode, reviewer token, and future provider keys must stay out of git. |
| Logs/rollback evidence | 10 | The portfolio must show operational proof, not only a URL. |
| Free-tier caveat clarity | 10 | Non-claims must be easy to explain in interview. |

## Options Compared

| Platform | Cost/spend risk | Docker/FastAPI fit | HTTPS reviewer URL | Env/secrets | Logs/rollback | Caveats |
|---|---|---|---|---|---|---|
| Render Free Web Service | Strong: free web services are supported, but usage limits apply and free web services are explicitly not for production apps. | Strong: Python/web service and Docker deploy paths are supported. | Strong: managed TLS certificates are listed for free web services. | Strong: Render supports environment variables/secrets. | Medium-strong: logs and rollback support exist, but rollback on free is limited to recent deploys. | Free service spins down after idle, cold start can take about a minute, filesystem is ephemeral, and free instances can be suspended on usage limits. |
| Fly.io | Medium: resource allowance exists, but dedicated IPv4 is paid and pricing is usage-based. | Strong: Docker-native app platform. | Strong: public networking and TLS support. | Strong: secrets support. | Strong: production-style platform with logs/metrics. | More operational surface and spend awareness than needed for a no-cost reviewer demo. |
| Railway Free | Medium: free plan starts with a trial/credits and later has a monthly charge; resource limits are small. | Strong: GitHub/Docker deployment supported. | Strong: app deployment is straightforward. | Strong: project variables/secrets are standard. | Medium: log history and availability targets improve on paid tiers. | Trial/credit semantics make “cost-free” less clean for a durable reviewer URL. |

## Decision

Use **Render Free Web Service** as the recommended first hosted reviewer demo
target, after explicit owner approval and account/login availability.

Reasons:

- It best matches the first-phase requirement: public HTTPS URL, low setup
  burden, and no provider credentials.
- Its free-tier limitations are explicit enough to document as non-production
  caveats: cold start, ephemeral filesystem, usage limits, no live-traffic SLO.
- The repo can keep a one-command local/container fallback and use
  `rfp_rag.hosted_demo_smoke` to prove the hosted reviewer contract after
  deployment.

## Non-Decision

This ADR does not approve external deployment, cloud credentials, paid services,
DNS, provider API usage, or live-traffic production claims. Those require a
separate explicit approval immediately before execution.

## Implementation Notes

- Hosted env vars:
  - `RFP_RAG_PUBLIC_DEMO_MODE=1`
  - `RFP_RAG_REVIEWER_TOKEN=<owner-provided reviewer token>`
  - `RFP_RAG_RATE_LIMIT_PER_MINUTE=<small integer>`
- Smoke command after deployment:

```bash
uv run python -m rfp_rag.hosted_demo_smoke \
  --base-url https://<render-service-url> \
  --reviewer-token "$RFP_RAG_REVIEWER_TOKEN"
```

## Evidence Sources

- Render free service docs: https://render.com/docs/free
- Fly.io pricing docs: https://fly.io/docs/about/pricing/
- Railway pricing docs: https://railway.com/pricing

## Re-Evaluation Conditions

- Render Free no longer supports the required web service shape.
- Cold start makes the reviewer demo unreliable even with a documented warm-up.
- The owner approves a paid always-on SaaS phase.
- The demo begins to require persistent storage, multi-tenant accounts, or
  real-provider execution.
