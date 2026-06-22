# Hosted Deployment Readiness Plan

This is production-facing readiness evidence, not a public deployment claim.
Public exposure, cloud credentials, paid services, DNS, and externally reachable
URLs require explicit owner approval before execution.

## Target Shape

- Runtime: containerized FastAPI service behind a managed HTTPS ingress.
- Local reviewer profile: the checked-in service exposes a local/container
  reviewer API surface only. Public hosted auth is not claimed by default.
- Auth boundary: reviewer demo uses local mode; hosted mode requires a signed
  reviewer token or identity-provider session before query, trace, or artifact
  access.
- Rate limit boundary: per-token request rate, per-minute streaming budget, and
  per-run max tool-call budget must fail closed before provider calls.
- Secret handling: `OPENAI_API_KEY`, tracing keys, and deployment secrets stay in
  environment or secret manager only; no persisted trace or screenshot may store
  raw secrets, raw prompts, raw tool inputs, or full RFP source text.
- Observability: hosted mode must export redacted traces, latency p50/p95,
  token/cost summaries, tool-call success/failure, and failed-run analysis.
- Rollback: deployment health check, credential-free regression, and local
  portfolio check must pass before traffic is enabled.
- Container hardening: runtime image uses a non-root user and Docker
  `HEALTHCHECK` for `/healthz`.
- Service failure contract: synchronous endpoints use structured HTTP errors;
  SSE emits `event: error` and terminates on guardrail/runtime failure.

## Non-Claims

- This repository does not claim live-traffic SLOs until hosted traffic exists.
- It does not claim multi-tenant isolation until auth/session boundaries are
  implemented and tested against a deployed endpoint.
- It does not publish dashboard screenshots unless the publishable allowlist and
  redaction scan pass.
