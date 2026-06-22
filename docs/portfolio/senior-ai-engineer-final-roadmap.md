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

1. R1: reviewer narrative and architecture diagram.
2. R6: company-fit matrix, because it sharpens what to emphasize.
3. R2: retrieval/parser quality, because this is the most important technical
   differentiator for document-heavy Korean RAG roles.
4. R3: agentic workflow depth, because it separates agent engineer from RAG
   integrator.
5. R4: production operations, because Tier A roles expect operating maturity.
6. R5: security/red-team, because it makes the project feel enterprise-ready.
7. R7: public presentation, after the technical claims are true.

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
