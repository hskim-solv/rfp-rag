#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8017}"
BASE_URL="http://${HOST}:${PORT}"
REVIEWER_TOKEN="${RFP_RAG_REVIEWER_TOKEN:-local-review-token}"
DEPLOYED_GIT_SHA="${DEPLOYED_GIT_SHA:-$(git rev-parse --short HEAD)}"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "== local hosted-profile server =="
RFP_RAG_PUBLIC_DEMO_MODE=1 \
RFP_RAG_REVIEWER_TOKEN="$REVIEWER_TOKEN" \
RFP_RAG_RATE_LIMIT_PER_MINUTE=20 \
RFP_RAG_GIT_SHA="$DEPLOYED_GIT_SHA" \
uv run uvicorn rfp_rag.service.app:app --host "$HOST" --port "$PORT" \
  >/tmp/rfp-local-hosted-demo-smoke.log 2>&1 &
SERVER_PID="$!"

for _ in {1..40}; do
  if python3 - "$BASE_URL/healthz" <<'PY'
import sys
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=1) as response:  # noqa: S310
        raise SystemExit(0 if response.status == 200 else 1)
except Exception:
    raise SystemExit(1)
PY
  then
    break
  fi
  sleep 0.25
done

python3 - "$BASE_URL/healthz" <<'PY'
import sys
import urllib.request

with urllib.request.urlopen(sys.argv[1], timeout=3) as response:  # noqa: S310
    if response.status != 200:
        raise SystemExit(f"healthz returned {response.status}")
PY

echo "== local hosted-profile smoke =="
uv run python -m rfp_rag.hosted_demo_smoke \
  --base-url "$BASE_URL" \
  --reviewer-token "$REVIEWER_TOKEN" \
  --expected-git-sha "$DEPLOYED_GIT_SHA" \
  --out artifacts/hosted_demo_smoke/summary.json

echo
echo "local_hosted_demo_smoke_ok=true"
