#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

HF_SPACE_ID="${HF_SPACE_ID:-hskim-solv/rfp-rag-reviewer-demo}"
DEPLOYED_GIT_SHA="${DEPLOYED_GIT_SHA:-$(git rev-parse --short HEAD)}"
: "${RFP_RAG_REVIEWER_TOKEN:?RFP_RAG_REVIEWER_TOKEN must be set; generate one locally and do not commit it}"

STAGE_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$STAGE_DIR"
}
trap cleanup EXIT

cp deploy/hf-space/README.md "$STAGE_DIR/README.md"
cp deploy/hf-space/Dockerfile "$STAGE_DIR/Dockerfile"
cp pyproject.toml uv.lock "$STAGE_DIR/"
cp -R rfp_rag "$STAGE_DIR/rfp_rag"

echo "== create/update Hugging Face Docker Space =="
uv run python - "$HF_SPACE_ID" "$DEPLOYED_GIT_SHA" <<'PY'
import os
import sys
from huggingface_hub import HfApi

space_id, deployed_git_sha = sys.argv[1:3]
reviewer_token = os.environ["RFP_RAG_REVIEWER_TOKEN"]
api = HfApi()
api.create_repo(
    repo_id=space_id,
    repo_type="space",
    space_sdk="docker",
    exist_ok=True,
)
api.add_space_variable(space_id, "RFP_RAG_PUBLIC_DEMO_MODE", "1")
api.add_space_variable(space_id, "RFP_RAG_RATE_LIMIT_PER_MINUTE", "20")
api.add_space_variable(space_id, "RFP_RAG_GIT_SHA", deployed_git_sha)
api.add_space_secret(
    space_id,
    "RFP_RAG_REVIEWER_TOKEN",
    value=reviewer_token,
)
print(f"space_id={space_id}")
PY

echo
echo "== upload Space bundle =="
hf upload "$HF_SPACE_ID" "$STAGE_DIR" . \
  --repo-type space \
  --commit-message "Deploy public-safe RFP reviewer demo"

SPACE_HOST="$(echo "$HF_SPACE_ID" | tr '/' '-' | tr '_' '-')"
SERVICE_URL="https://${SPACE_HOST}.hf.space"

echo
echo "SERVICE_URL=$SERVICE_URL"
echo "DEPLOYED_GIT_SHA=$DEPLOYED_GIT_SHA"
