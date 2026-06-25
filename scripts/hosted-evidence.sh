#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${SERVICE_URL:?SERVICE_URL must be the approved HTTPS hosted demo URL}"
: "${RFP_RAG_REVIEWER_TOKEN:?RFP_RAG_REVIEWER_TOKEN must be set from the hosted reviewer secret}"
: "${CONFIRM_LOGS_REDACTED:?set CONFIRM_LOGS_REDACTED=true only after checking hosted logs}"
: "${CONFIRM_METRICS_VISIBLE:?set CONFIRM_METRICS_VISIBLE=true only after checking hosted metrics}"
: "${CONFIRM_ROLLBACK_RUNBOOK:?set CONFIRM_ROLLBACK_RUNBOOK=true only after checking rollback evidence}"

if [[ "$SERVICE_URL" != https://* ]]; then
  echo "SERVICE_URL must be an HTTPS hosted URL" >&2
  exit 2
fi

if [[ "$CONFIRM_LOGS_REDACTED" != "true" ]]; then
  echo "CONFIRM_LOGS_REDACTED must be true" >&2
  exit 2
fi

if [[ "$CONFIRM_METRICS_VISIBLE" != "true" ]]; then
  echo "CONFIRM_METRICS_VISIBLE must be true" >&2
  exit 2
fi

if [[ "$CONFIRM_ROLLBACK_RUNBOOK" != "true" ]]; then
  echo "CONFIRM_ROLLBACK_RUNBOOK must be true" >&2
  exit 2
fi

DEPLOYED_GIT_SHA="${DEPLOYED_GIT_SHA:-$(git rev-parse --short HEAD)}"
HOSTED_PROVIDER="${HOSTED_PROVIDER:-render}"

echo "== hosted demo smoke =="
uv run python -m rfp_rag.hosted_demo_smoke \
  --base-url "$SERVICE_URL" \
  --reviewer-token "$RFP_RAG_REVIEWER_TOKEN" \
  --expected-git-sha "$DEPLOYED_GIT_SHA" \
  --out artifacts/hosted_demo_smoke/summary.json

echo
echo "== hosted ops summary =="
uv run python -m rfp_rag.hosted_ops_summary \
  --service-url "$SERVICE_URL" \
  --deployed-git-sha "$DEPLOYED_GIT_SHA" \
  --provider "$HOSTED_PROVIDER" \
  --out artifacts/hosted_ops/summary.json \
  --confirm-logs-redacted \
  --confirm-metrics-visible \
  --confirm-rollback-runbook

echo
echo "== hosted deployment evidence =="
uv run python -m rfp_rag.hosted_deployment_evidence \
  --out artifacts/hosted_deployment_evidence/summary.json

echo
echo "== production readiness =="
uv run python -m rfp_rag.production_readiness \
  --out artifacts/production_readiness/summary.json

echo
echo "== final portfolio scorecard =="
uv run python -m rfp_rag.final_portfolio_scorecard \
  --out artifacts/final_portfolio_scorecard/summary.json

echo
echo "== portfolio check =="
uv run python -m rfp_rag.portfolio_check \
  --out artifacts/portfolio_readiness.json

echo
echo "hosted_evidence_ok=true"
