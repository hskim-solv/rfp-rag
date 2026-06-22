# Senior AI Engineer Final Roadmap

Date: 2026-06-22

This roadmap defines what remains for `rfp-rag` to read as a top-tier senior AI
engineer portfolio, using the local career targeting report as the primary
market lens:

- Reference: `/Users/hskim/Desktop/projects/ai-career-targeting/reports/tiered_company_list.html`
- Report snapshot: Tier A 21 roles, Tier B 107 roles.
- Dominant categories in that report: `ai_general`, `ml`, `recommendation_search`,
  `llm`, `agent`, `vision`, `rag`, `multimodal`, `nlp`, `fde`, `ax`.
- Directly relevant sampled role families: AI/Data Platform Engineer, Enterprise
  GenAI Platform, Senior AI Agent Engineer, AI Agent Platform Engineering,
  AI Research Engineer - Agents & Workflows, LLM Serving Platform, LLM Eval,
  MLOps Engineer, Search Ranking, Forward Deployed Engineer - LLM.

External Korean-market check on 2026-06-22 showed the same signal: current AI
Agent/RAG roles repeatedly ask for LangChain/LangGraph, RAG, tool calling,
multi-agent or agentic workflow, LLM-as-a-judge evaluation, tracing/debugging,
MLOps/LLMOps or AgentOps, Docker/CI/CD, and business-process automation.

## Market Evidence

The local report is the primary targeting input, but the final roadmap also
tracks public Korean-market job signals checked on 2026-06-22:

| Source | Repeated signal | Portfolio implication |
| --- | --- | --- |
| Kakao Healthcare AI Agent Engineer on Wanted | LLM API, prompt engineering, RAG, tool calling, LangChain/LangGraph/ADK, AI coding tools | Keep `rfp-rag` framed as an AI agent application, not only retrieval. Show tool calling, graph control flow, and API service work. |
| Hits AI Agent Engineer | LangChain/LangGraph/LlamaIndex, RAG, MCP, agent application design/build/deploy, domain data adaptation | Preserve MCP/tool-server lane and emphasize domain-heavy public RFP workload. |
| Livedata AI Backend Engineer on Wanted | RAG, Agentic AI Workflow, MCP/A2A API, LangChain/LangGraph reasoning graph, LLM-as-a-judge | Add agent workflow evaluation and API contract proof, not only offline metrics. |
| Agilesoda AI Agent Engineer on Wanted | Advanced RAG, hybrid search, multi-agent collaboration, function calling, AgentOps/LLMOps | Prioritize reranking/hybrid retrieval, guardrails, and observability. |
| Adriel AI Agent Engineer on Wanted | LangChain/LangGraph, Knowledge Base, Vector/Graph RAG, LangSmith tracing/evaluation/debugging | Add company-fit variant for commercial SaaS AgentOps and tracing. |
| Upstage careers | Agents & Workflows, LLM Eval, LLM Serving Platform | Keep the project evaluation-heavy and service-runtime credible. |

Conclusion: the roadmap should optimize for "agentic RAG system that is
measured, operated, and safe" rather than "many AI features."

## Final Portfolio Claim

Target claim:

> Built a source-first production-grade Agentic RAG system for Korean public RFP
> documents, with parsing quality control, retrieval evaluation, LangGraph agent
> orchestration, tool budget and guardrails, traceable operations, Dockerized API
> service, CI gates, and reviewer-ready evidence that turns unstructured public
> procurement documents into auditable answers with citations.

This should position the project for three role clusters:

1. Senior AI Agent Engineer / Agent Platform Engineer.
2. RAG / LLM Application Engineer for enterprise or domain-heavy products.
3. AI Platform / MLOps / LLMOps engineer who can productionize AI systems.

It should not be positioned primarily as model research, fine-tuning, robotics,
or multimodal generation.

## North Star Bar

The portfolio is complete only when a reviewer can answer all of these within
10 minutes:

- What real business problem is solved?
- Why is this harder than a toy chatbot?
- What is the source of truth?
- How is answer quality measured?
- How are hallucination, prompt injection, tool abuse, cost, and latency bounded?
- How does the agent recover or ask for human approval?
- Can the service run in a container and be tested in CI?
- What evidence proves the author can operate and debug it?

## Senior Portfolio Scorecard

Use this as the acceptance rubric before treating the project as interview-ready
for Tier A roles.

| Dimension | Weight | Target evidence | Current status |
| --- | ---: | --- | --- |
| Business problem sharpness | 10 | Korean public RFP workload, concrete user, before/after workflow, demo script | Strong baseline; needs final reviewer narrative polish. |
| Source-first RAG quality | 20 | Parser quality report, citation audit, holdout metrics, retrieval ablation | Good baseline; biggest remaining differentiator. |
| Agentic engineering depth | 20 | LangGraph state, conditional routing, retry/reflection, tools, HITL, checkpoint replay | Strong baseline; needs multi-step task demo and recovery metrics. |
| Evaluation rigor | 15 | Golden set, real judge lane, regression gates, failure taxonomy, metric thresholds | Strong baseline; expand holdout and adversarial sets. |
| Production operations | 15 | Docker, CI smoke, tracing, latency/cost/token report, runbook, release artifact | Production-complete baseline achieved; improve dashboard/demo visibility. |
| Guardrails/security | 10 | prompt injection tests, tool allowlist, budget limits, PII/secrets leakage checks | Baseline present; needs red-team pack and score report. |
| Hiring presentation | 10 | README case study, 10-minute reviewer script, diagrams, company-fit variants, video | Needs final packaging. |

Target score before applying: >= 90/100.

Failure threshold:

- < 80: strong project, but not yet top-tier senior portfolio.
- 80-89: credible senior portfolio, but interviewer may still see it as
  production-adjacent rather than production-grade.
- >= 90: strong enough to lead with in senior AI Agent/RAG interviews.

## Current Production-Complete Baseline

Already achieved by the current production-complete PR:

- FastAPI service surface with `/healthz`, `/v1/gates`, `/v1/answer`.
- Docker hardening with non-root user and healthcheck.
- CI Docker runtime smoke for service startup and answer error contract.
- Structured API error and SSE error event contract.
- LangGraph agent lane with state/checkpoint/HITL evidence.
- Offline credential-free test lane and real-lane quality artifacts.
- Stage2 judge recovery and evidence integrity checks.
- `production_readiness` and `portfolio_check` fail-closed artifacts.
- Reviewer evidence docs and 10-minute reviewer script.

This is a strong senior portfolio baseline. The remaining roadmap is not needed
to prove "can build"; it is needed to make the project feel undeniably top-tier
against Tier A roles.

## Roadmap

### R1. Reviewer Narrative And Demo Package

Goal: make the project instantly legible to hiring managers and senior engineers.

Deliverables:

- `docs/portfolio/senior-reviewer-pack.md`: one page with problem, architecture,
  quality numbers, failure modes, and commands.
- 3-5 minute demo video script and shot list.
- Architecture diagram showing ingestion, parser artifacts, index, retriever,
  LangGraph agent, tools, guardrails, tracing, eval gates, and CI.
- Resume bullets mapped to concrete evidence files.

Quality bar:

- A reviewer can run `scripts/reviewer-10m.sh` and understand the system without
  reading implementation internals.
- Every resume claim links to a command, artifact, or source file.

Failure condition:

- The project still reads like "I connected LangChain to a vector DB" instead of
  "I engineered and measured a domain AI system."

### R2. Retrieval Quality And Parser Semantics

Goal: make RAG quality look defensible, not anecdotal.

Deliverables:

- Parser/render bakeoff report for HWP/PDF documents, including tables and
  visual layout failure cases.
- Retrieval ablation: baseline vector search vs hybrid search vs reranker.
- Source-first citation audit: answer spans must map back to parsed document
  evidence, not only metadata rows.
- Larger golden set split into smoke, regression, holdout, and adversarial cases.

Target metrics:

- Citation precision >= 0.90 on holdout.
- Unsupported claim rate <= 0.03.
- Context recall >= 0.75 on source-first questions.
- Context precision >= 0.70 after reranking.
- Answer faithfulness >= 0.85 on real judge lane.
- Regression suite has zero known high-severity misses.

Failure condition:

- Quality claims depend on a small or hand-picked eval set.
- CSV metadata can still accidentally become the answer source of truth.

### R3. Agentic Workflow Depth

Goal: prove this is an agent system with controlled decision-making, not a
single retrieval chain.

Deliverables:

- Clear planner-executor or supervisor-worker path for multi-step RFP analysis.
- Tool contracts for document retrieval, SQL-style metadata query, web search or
  public notice lookup, internal policy lookup, and report generation.
- State replay and checkpoint resume demo for interrupted analysis.
- Human approval path for actions that save, export, or rely on low-confidence
  evidence.
- Adversarial workflow cases: ambiguous question, conflicting evidence, missing
  document, prompt injection in document text, oversized tool output.

Target metrics:

- Agent task success >= 0.80 on multi-step golden cases.
- Tool-call success rate >= 0.95 in offline lane.
- Recovery success >= 0.85 when first retrieval is insufficient.
- Max tool-call budget enforced in 100% of tests.
- HITL approval path covered by tests and demo artifact.

Failure condition:

- Agent graph exists, but the reviewer cannot see why LangGraph/state/checkpoint
  is necessary.

### R4. Production Operations And LLMOps

Goal: match Tier A platform/MLOps expectations.

Deliverables:

- Trace dashboard artifact using Langfuse, Phoenix, or an equivalent local
  report.
- Run-level observability: latency, tokens, cost, tool success/failure,
  retrieval hit quality, judge coverage, and error taxonomy.
- Load and latency smoke for local service.
- Release runbook: build, deploy, rollback, rotate secrets, rebuild index,
  recover failed eval, inspect traces.
- Hosted deployment option with auth/rate-limit only after explicit approval.

Target metrics:

- `/healthz` p95 < 200 ms locally.
- `/v1/answer` p95 target documented separately for fake and real providers.
- Cost per evaluated answer reported for real lane.
- 100% production-readiness checks produce machine-readable artifacts.
- All external/paid calls have explicit env-gated execution.

Failure condition:

- The project has good tests but no operational story for debugging a bad answer
  or failed run.

### R5. Security, Guardrails, And Red Teaming

Goal: show mature AI risk handling.

Deliverables:

- Prompt injection test pack for retrieved documents and user questions.
- Tool allowlist and deny-by-default behavior documented with tests.
- PII/secrets leakage checks for logs, traces, and generated reports.
- Output size cap, timeout, retry, and budget enforcement for every tool path.
- Red-team report with accepted risks, mitigations, and residual risks.

Target metrics:

- Prompt injection pass rate >= 0.95 on regression pack.
- Secret/PII leak tests: zero known leaks.
- Tool budget violation tests: 100% blocked.
- Unsafe save/export paths require HITL approval.

Failure condition:

- Guardrails are described in README but not exercised by tests.

### R6. Company-Fit Portfolio Variants

Goal: make the same project speak directly to different target companies.

Deliverables:

- `docs/portfolio/company-fit-matrix.md` with tailored narratives:
  - Upstage / agent workflow / eval: agent quality, LLM-as-judge, workflow design.
  - NAVER/Kakao-style platform: reliability, observability, service boundaries.
  - Coupang/Moloco/search-recommendation: retrieval/ranking ablation and metrics.
  - Enterprise GenAI / AX: document workflow automation, approval, auditability.
  - Legal/public-sector/document AI: source-first citations and high trust.
  - FDE/solution engineering: customer problem framing, deployment runbook.
- Short Korean one-page case study for domestic interviewers.
- English version for global roles.

Quality bar:

- Each variant has one headline, three proof bullets, and exact evidence links.
- No variant exaggerates beyond current artifacts.

Failure condition:

- One generic README is expected to satisfy all role families.

### R7. Public Presentation And Hiring Surface

Goal: make the portfolio usable outside the local machine.

Deliverables:

- Final README top section rewritten as a senior case study, not a package manual.
- Public-safe sample artifacts with no raw sensitive content.
- Demo screenshots or video.
- Optional public hosted demo with limited fake-provider mode, auth boundary, and
  cost-safe rate limits.
- GitHub release tag with final evidence snapshot.

Target metrics:

- Fresh clone can run offline smoke without credentials.
- Reviewer pack works from README in under 10 minutes.
- Public demo, if enabled, cannot trigger paid model calls or raw artifact leaks.

Failure condition:

- The best evidence remains hidden in local artifacts that reviewers cannot
  inspect or reproduce.

## Execution Order

### Stage 0. Freeze The Current Baseline

Purpose: preserve the production-complete proof already achieved.

Exit criteria:

- PR contains the current production-readiness proof.
- `portfolio_check` and `production_readiness` are green.
- README and reviewer docs do not overclaim public/cloud deployment.

### Stage 1. Make The Reviewer Story Unmissable

Purpose: convert the repo from "technically rich" to "obviously senior."

Implement:

- R1 reviewer narrative and architecture diagram.
- R6 company-fit matrix.
- README top rewrite as a case study.

Exit criteria:

- A reviewer can understand problem, architecture, quality, operations, and
  risks in under 10 minutes.
- Every major claim links to an artifact or command.

### Stage 2. Make RAG Quality Hard To Dismiss

Purpose: win document-heavy RAG interviews.

Implement:

- R2 parser/render bakeoff.
- Retrieval ablation.
- Citation audit.
- Expanded golden/holdout/adversarial eval sets.
- Deterministic Stage 2 RAG quality scorecard:
  `rfp_rag.stage2_quality_scorecard` ->
  `artifacts/stage2_quality_scorecard/summary.json`.

Exit criteria:

- Metrics meet R2 thresholds.
- `stage2_quality_scorecard_complete=true` and `failed=[]`.
- The failure report shows known weaknesses and concrete mitigations.

### Stage 3. Make The Agent Layer Nontrivial

Purpose: win AI Agent Engineer interviews.

Implement:

- R3 multi-step planner-executor or supervisor-worker scenario.
- Tool contracts and checkpoint replay demo.
- Recovery and HITL approval metrics.

Exit criteria:

- Reviewer can see why graph state, retries, checkpoints, and HITL are necessary.
- Agent task metrics meet R3 thresholds.

### Stage 4. Make Operations And Risk Management Visible

Purpose: win senior/platform-oriented interviews.

Implement:

- R4 observability dashboard/report.
- R5 red-team and guardrail scorecard.
- Release runbook and operational failure playbook.

Exit criteria:

- A bad answer can be traced from API request to retrieval, tool calls, judge
  result, and final error/fallback behavior.
- Guardrail metrics meet R5 thresholds.

### Stage 5. Publish The Hiring Surface

Purpose: make the portfolio externally consumable.

Implement:

- R7 final README, public-safe artifacts, screenshots/video.
- Optional hosted fake-provider demo only if explicitly approved.
- Final GitHub release tag.

Exit criteria:

- Fresh clone works without credentials.
- Public-facing materials do not expose raw RFP text, secrets, or paid-call
  paths.
- Company-fit variants are ready for resume/interview use.

## Definition Of Done

The final roadmap is complete when:

- `portfolio_check` and `production_readiness` both report `failed=[]`.
- Retrieval, agent, guardrail, and ops metrics meet the thresholds above.
- The reviewer pack, company-fit matrix, and README all tell the same story.
- The system can be demonstrated offline without credentials and optionally in
  a public-safe mode without paid-call risk.
- A senior interviewer can point to at least three nontrivial engineering
  decisions: source-first evidence, measured retrieval quality, controlled agent
  workflow, production operations, or AI security.

## Non-Goals

- Full model fine-tuning or custom SLM training.
- RLHF pipeline.
- Robotics or physical AI.
- Broad multimodal generation.
- Kubernetes/Terraform unless a target role specifically requires platform
  infrastructure proof.

## User Decisions Required Later

- Whether to add a public hosted demo.
- Whether to spend real API budget for a larger final holdout.
- Which target company cluster gets the first tailored README/resume variant.
- Whether to add cloud deployment evidence or keep the project local/CI-only.
