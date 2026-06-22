# Korean Senior AI Agent Engineer Reviewer Evidence Map

This is the 10-minute reviewer path for judging this repository as a senior AI
Agent Engineer portfolio. It is intentionally evidence-first: every claim below
has a local artifact, command, or document that can be inspected without provider
credentials.

## One-line Claim

Production-adjacent Agentic RAG backend for Korean public RFP intelligence:
source-first document parsing, citation-grounded retrieval, typed LangGraph
workflow, FastAPI/SSE service surface, guardrails, observability summaries, and
fail-closed evaluation gates.

## 10-minute Review Path

| minute | what to inspect | evidence |
|---:|---|---|
| 0-1 | Scope and non-claims | `README.md` Portfolio Status; this is local/container evidence, not hosted production |
| 1-2 | Architecture shape | `docs/architecture/system-architecture.md` logical/runtime/agent diagrams |
| 2-3 | Gate freshness | `python3 -m rfp_rag.gate_status` should report `overall_ok=true` |
| 3-4 | Portfolio contract | `artifacts/portfolio_readiness.json` should show `portfolio_readiness_check=true` and `interview_readiness_check=true` |
| 4-5 | RAG quality | `artifacts/eval_real/metrics.json`, `artifacts/eval_stage3_holdout/metrics.json` |
| 5-6 | Agent workflow | `artifacts/eval_agent_stress/metrics.json`, `artifacts/agent_orchestration/summary.json` |
| 6-7 | Service/streaming/ops | `artifacts/service_ops/summary.json`, `artifacts/top_tier_demo/summary.json` |
| 7-8 | Observability and failures | `artifacts/observability/summary.json`, `docs/portfolio/failed-run-analysis.md`, `docs/evidence/demo-package/03-trace-failure-cost.md` |
| 8-9 | Security and dependency hygiene | `artifacts/security_redteam/summary.json`, `artifacts/reliability_security/summary.json`, `artifacts/security_alerts/summary.json` |
| 9-10 | Senior judgment | `docs/portfolio/korean-one-page-case-study.md`, `docs/portfolio/case-study.md`, `docs/portfolio/tool-contract-matrix.md`, `docs/portfolio/resume-interview-bullets.md` |

## Current Quantitative Evidence

| area | target signal | current evidence |
|---|---|---|
| Fresh gates | stale evidence fails closed | `gate_status overall_ok=true` across offline, real, agent, visual lanes |
| Local reviewer demo | first verified answer within 5 minutes | `time_to_first_verified_answer_sec=21.72`, `top_tier_demo_complete=true` |
| Stage 3 holdout | fixed-corpus query holdout, >=100 queries, strong citation/faithfulness | `document_count=20`, `query_count=100`, `recall@5=1.0`, `mrr=1.0`, `citation_validity=1.0`, `faithfulness=0.9887`, `answer_relevancy=0.8797`; not an unseen-document or public-traffic benchmark |
| LangGraph agent | typed workflow, retry/reflection, HITL/checkpoint, audit | `trajectory_pass_rate=1.0`; planner-executor evidence is scenario replay evidence, not a dynamic planner runtime claim |
| Service surface | API, SSE, gates, ops summary | `healthz_pass=1.0`, `answer_pass=1.0`, `stream_pass=1.0`, `gates_pass=1.0`, `ops_summary_pass=1.0`, `full_answer_smoke=true`, `full_gates_smoke=true` |
| Observability | trace export, latency, cost, tool outcomes, failure analysis | `trace_provider=local_redacted_artifact_export`, `trace_export_present=1.0`, `failed_run_analysis_count=5`; this is local redacted evidence, not provider telemetry |
| Security/reliability | prompt injection, secrets/PII, fallback, deterministic replay | `redteam_case_count=20`, `prompt_injection_block_recall=1.0`, `secrets_pii_leak_count=0` |
| Dependency hygiene | no unresolved unaccepted alert | `open_alerts=[]`, `diskcache_absent=1.0`, `langchain_patched=1.0` |

## What To Say In An Interview

This project is not sold as a chatbot. The engineering claim is that a
source-sensitive Korean RFP workload has been turned into a measurable backend
system: parsing, chunking, retrieval, generation, agent orchestration, service
contracts, security checks, observability summaries, cost estimates, and CI all
produce artifacts that can be regenerated or fail closed.

The senior signal is the restraint: vector retrieval remains the default because
BM25/hybrid did not beat it on the same frozen set, and no reranker win is claimed
until a same-set paid/API artifact proves quality without latency, citation,
abstention, or cost regression.

For a Korean interview summary, use
`docs/portfolio/korean-one-page-case-study.md` before opening the longer English
case study.

## Non-claims And Approval Boundaries

| non-claim | why it is not claimed yet | approval needed before doing it |
|---|---|---|
| Hosted cloud production | no public deployment, live traffic, auth session, or incident history exists | yes: cloud provider, spend, public exposure |
| Public dashboard | dashboard scope changes data disclosure and UI surface | yes: publishable artifact/source policy |
| Provider billing telemetry | current cost evidence is deterministic from persisted predictions | yes: provider telemetry/API access |
| Live-traffic SLO | no real user traffic or monitoring window exists | yes: deployed service and monitoring scope |
| Reranker quality win | reranker interface exists, but no same-set winning artifact is accepted | yes: paid/API reranker run or new provider adoption |

## Verification Commands

```bash
./scripts/reviewer-10m.sh
uv run python -m rfp_rag.gate_status
uv run python -m rfp_rag.portfolio_check --out artifacts/portfolio_readiness.json
uv run python -m pytest -m "not real" -q
```

The portfolio claim should be paused if any command fails, if `failed` is not an
empty list in the relevant artifact, or if a newer artifact uses a different
contract without the README and gate code being updated together.

If `eval_stage2_real` fails only on `prediction_judge_coverage_*`, use the
judge-only recovery command after paid/API approval:
`uv run python -m rfp_rag.stage2_rejudge_missing`. It rejudges only missing
Stage 2 rows, then reaggregates and finalizes the Stage 2 contract.
