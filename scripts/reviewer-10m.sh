#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== RFP Senior AI Agent Engineer reviewer pack =="
echo "root=$ROOT"

echo
echo "== gate_status =="
uv run python -m rfp_rag.gate_status

echo
echo "== stage2_quality_scorecard =="
uv run python -m rfp_rag.stage2_quality_scorecard --out artifacts/stage2_quality_scorecard/summary.json

echo
echo "== agent_orchestration =="
uv run python -m rfp_rag.agent_orchestration

echo
echo "== stage3_agent_scorecard =="
uv run python -m rfp_rag.stage3_agent_scorecard --out artifacts/stage3_agent_scorecard/summary.json

echo
echo "== production_readiness =="
uv run python -m rfp_rag.production_readiness --out artifacts/production_readiness/summary.json

echo
echo "== stage4_ops_risk_scorecard =="
uv run python -m rfp_rag.stage4_ops_risk_scorecard --out artifacts/stage4_ops_risk_scorecard/summary.json

echo
echo "== fresh_clone_smoke =="
uv run python -m rfp_rag.fresh_clone_smoke --out artifacts/fresh_clone_smoke/summary.json

echo
echo "== final_portfolio_scorecard =="
uv run python -m rfp_rag.final_portfolio_scorecard --out artifacts/final_portfolio_scorecard/summary.json

echo
echo "== portfolio_check =="
uv run python -m rfp_rag.portfolio_check --out artifacts/portfolio_readiness.json

echo
echo "== credential-free tests =="
uv run python -m pytest -m "not real" -q

echo
echo "== key artifacts =="
for path in \
  docs/portfolio/senior-reviewer-pack.md \
  docs/portfolio/company-fit-matrix.md \
  docs/portfolio/reviewer-evidence-map.md \
  docs/portfolio/korean-one-page-case-study.md \
  artifacts/portfolio_readiness.json \
  artifacts/stage2_quality_scorecard/summary.json \
  artifacts/stage3_agent_scorecard/summary.json \
  artifacts/stage4_ops_risk_scorecard/summary.json \
  artifacts/hosted_demo_smoke/summary.json \
  artifacts/fresh_clone_smoke/summary.json \
  artifacts/final_portfolio_scorecard/summary.json \
  artifacts/eval_real/metrics.json \
  artifacts/eval_stage2_real/metrics.json \
  artifacts/eval_stage3_holdout/metrics.json \
  artifacts/eval_agent_stress/metrics.json \
  artifacts/service_ops/summary.json \
  artifacts/security_redteam/summary.json \
  artifacts/observability/summary.json
do
  if [[ -f "$path" ]]; then
    echo "present $path"
  else
    echo "missing $path"
    exit 1
  fi
done

echo
echo "reviewer_pack_ok=true"
