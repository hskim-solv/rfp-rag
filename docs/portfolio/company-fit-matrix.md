# Company Fit Matrix

Date: 2026-06-22

Primary input: `/Users/hskim/Desktop/projects/ai-career-targeting/reports/tiered_company_list.html`.
The local report contains Tier A 21 roles and Tier B 107 roles. The most
relevant recurring categories for this repo are `agent`, `rag`, `llm`,
`ai_general`, `ml`, `recommendation_search`, `nlp`, `fde`, `ax`, and `MLOps`.

This matrix keeps the portfolio story honest: one technical project, several
role-specific framings, no new unsupported claims. The shared claim is a
public-safe hosted reviewer demo for Korean public RFPs backed by
local/container reproducibility evidence, not full hosted production SaaS,
live-traffic SLO, or provider billing telemetry.

## Positioning Summary

| target cluster | fit | lead with | do not lead with |
| --- | --- | --- | --- |
| Senior AI Agent Engineer / Agent Platform | strongest | LangGraph state, tool use, HITL, checkpoint replay, guardrails, eval gates | generic chatbot UX |
| RAG / LLM Application Engineer | strongest | source-first parsing, citation quality, retrieval bakeoff, holdout metrics | raw CSV Q&A |
| AI Platform / MLOps / LLMOps | strong | Docker, CI, readiness gates, tracing, cost/latency/tool outcome summaries | notebook experiments |
| Search / Recommendation ML | medium-strong | retrieval ablation, ranking metrics, recall/MRR/citation validity | generative answer demos only |
| Forward Deployed Engineer / AX | strong | business workflow automation, runbook, approval boundaries, customer-facing evidence | model novelty |
| LLM Serving / Infra | medium | FastAPI contract, Docker, local service smoke, timeout/output caps | large-scale serving or GPU claims |
| Research Scientist / Model Training | weak | evaluation rigor only | fine-tuning, RLHF, custom model training |
| Multimodal / Vision | weak-medium | visual/table evidence as document-AI support | broad multimodal generation |

## Role-family Mapping

| role family from report/public checks | matching evidence in this repo | interview pitch |
| --- | --- | --- |
| AI Agent Platform Engineering | `rfp_rag/agent`, LangGraph graph, HITL, checkpoints, `artifacts/eval_agent_stress/metrics.json` | "I can design controlled agent workflows where state, retries, approvals, and recovery are inspectable." |
| Senior AI Agent Engineer | service API, tool contracts, guardrails, eval artifacts, reviewer pack | "This is an agentic backend with bounded tools and measured outcomes, not prompt-only automation." |
| Enterprise GenAI Platform | FastAPI/Pydantic service, Docker, CI, production readiness, reviewer-token hosted boundary | "I can package GenAI capability behind service contracts and fail-closed gates." |
| RAG / Knowledge Base Engineer | source parsing, Qdrant index, citation validity, retrieval bakeoff, holdout metrics | "The RAG source of truth is parsed documents, and quality is measured across retrieval and generation." |
| RAG Quality / Evaluation Engineer | Stage 2 quality scorecard, deterministic context precision/recall, citation proxy, parser quality | "The quality claim is aggregated into a fail-closed scorecard instead of being scattered across ad hoc artifacts." |
| Agent Workflow Engineer | Stage 3 agent scorecard, replay coverage, HITL approve/reject, checkpoint/thread isolation | "The agent claim is backed by deterministic trajectory evidence, not just a graph diagram." |
| LLM Eval | real/stage2/stage3 metrics, judge coverage, thresholds, failed-run analysis | "The project treats evaluation as product infrastructure, not an afterthought." |
| MLOps / LLMOps / AgentOps | observability report, cost budget, service ops, security smoke, CI gates | "Bad answers and failed runs can be traced through request, retrieval, tool, judge, and artifact layers." |
| AI Risk / AgentOps Engineer | Stage 4 ops/risk scorecard, red-team gates, dependency security, hosted reviewer boundary | "The operating claim is bounded by measured evidence and explicit non-claims for full SaaS production and live SLOs." |
| Search Ranking / Recommendation Search | recall/MRR, vector/BM25/hybrid comparison, reranker deferral | "Retrieval choices are benchmarked and only promoted when they win on the same set." |
| FDE / AX Engineer | demo runbook, company-fit matrix, Korean case study, approval and deployment boundaries | "I can turn a messy business document workflow into a measurable AI system and explain trade-offs to stakeholders." |

## Company-style Variants

| company style | headline | proof bullets |
| --- | --- | --- |
| Upstage-style agent/eval/platform | Evaluation-heavy Agentic RAG backend for complex Korean documents | LangGraph workflow; LLM-as-judge style quality artifacts; service/runtime evidence; explicit non-claims |
| Kakao/NAVER-style platform | Reliable AI backend with source-grounded answers and local production gates | FastAPI/Pydantic; Docker/CI; structured errors/SSE failure; observability and security artifacts |
| Coupang/Moloco-style search/ranking | Retrieval system with measured ranking quality and conservative adoption decisions | recall/MRR; retrieval bakeoff; reranker deferred until same-set win; citation validity |
| Enterprise GenAI / AX | Auditable document intelligence workflow for procurement review | source-first RFP parsing; approval boundaries; reviewer runbook; ops/security/cost summaries |
| Healthcare/legal/public-sector document AI | High-trust answer generation with citations and guardrails | citation presence/validity; unsupported claim controls; prompt-injection/security tests; no raw source overexposure |
| FDE / solution engineering | Customer-facing AI workflow packaged with runbooks and evidence | 10-minute reviewer path; Korean one-page case study; deployment plan; failure playbook |

## Resume Variants

### AI Agent Engineer

- Built a source-first Agentic RAG backend for Korean public RFPs with typed
  LangGraph orchestration, conditional routing, bounded rewrite loops,
  checkpoint/HITL paths, guarded tool calls, and replayable agent stress
  artifacts.
- Exposed the workflow through FastAPI/Pydantic and SSE contracts with
  structured errors, Docker runtime smoke, and fail-closed portfolio gates.

### RAG / LLM Application Engineer

- Designed a document-grounded RAG pipeline where parsed HWP/PDF artifacts are
  the body source of truth and CSV is metadata only.
- Evaluated retrieval and generation with recall, MRR, faithfulness, answer
  relevancy, citation presence, citation validity, and same-set retrieval
  bakeoff decisions.

### AI Platform / LLMOps

- Added public-safe hosted reviewer evidence plus local/container
  reproducibility evidence: Docker non-root service, healthcheck, CI smoke,
  readiness artifacts, cost/latency summaries, observability exports, security
  smoke, and release/runbook documentation.
- Kept paid/API, full SaaS production, credential-risk, and cloud-spend paths
  explicitly approval-gated.

## Evidence Links

| claim | evidence |
| --- | --- |
| source-first RAG | `README.md`, `docs/architecture/system-architecture.md`, `rfp_rag/parse_sources.py` |
| agent workflow | `rfp_rag/agent`, `artifacts/eval_agent_stress/metrics.json` |
| agent workflow scorecard | `rfp_rag/stage3_agent_scorecard.py`, `artifacts/stage3_agent_scorecard/summary.json` |
| service runtime | `rfp_rag/service/app.py`, `Dockerfile`, `.github/workflows/ci.yml` |
| tool contracts | `docs/portfolio/tool-contract-matrix.md`, `rfp_rag/ops_tool_server.py` |
| readiness gates | `rfp_rag/portfolio_check.py`, `rfp_rag/production_readiness.py` |
| RAG quality scorecard | `rfp_rag/stage2_quality_scorecard.py`, `artifacts/stage2_quality_scorecard/summary.json` |
| ops/risk scorecard | `rfp_rag/stage4_ops_risk_scorecard.py`, `artifacts/stage4_ops_risk_scorecard/summary.json` |
| final portfolio scorecard | `rfp_rag/final_portfolio_scorecard.py`, `artifacts/final_portfolio_scorecard/summary.json` |
| hosted reviewer demo | `render.yaml`, `rfp_rag/hosted_demo_smoke.py`, `rfp_rag/hosted_deployment_evidence.py`, `artifacts/hosted_demo_smoke/summary.json`, `artifacts/hosted_deployment_evidence/summary.json` |
| fresh clone smoke | `rfp_rag/fresh_clone_smoke.py`, `artifacts/fresh_clone_smoke/summary.json` |
| reviewer path | `docs/portfolio/senior-reviewer-pack.md`, `scripts/reviewer-10m.sh`, `scripts/hosted-evidence.sh` |
| Korean interview story | `docs/portfolio/korean-one-page-case-study.md` |

## Non-fit And Non-claims

- Do not pitch this as full hosted production SaaS; the approved hosted claim is
  a constrained public-safe reviewer demo.
- Do not pitch this as model-training research, RLHF, custom SLM training, or
  robotics.
- Do not claim a reranker quality win until a same-set artifact proves it.
- Do not claim live provider billing telemetry unless the provider data exists.
