# Resume and Interview Bullets

Use these bullets only with the current local evidence bundle. Before submitting
or presenting, rerun:

```bash
python3 -m rfp_rag.gate_status
python3 -m rfp_rag.portfolio_check --out artifacts/portfolio_readiness.json
uv run python -m rfp_rag.production_readiness
uv run python -m pytest -m "not real" -q
```

The equivalent exact `python3 -m pytest` form is:

```bash
PATH="$PWD/.venv/bin:$PATH" python3 -m pytest -m "not real" -q
```

## Resume Bullets

- Built a production-adjacent Agentic RAG backend for 100 Korean public RFP
  HWP/PDF documents, using parsed source artifacts as the RAG body source of
  truth and CSV only as a metadata registry.
- Implemented FastAPI/Pydantic async service surfaces, SSE streaming checks,
  constrained LangGraph typed-state orchestration, guarded tool calls,
  checkpoint/HITL approval paths, and deterministic agent stress replay
  artifacts to reduce stale-evidence, uncontrolled-tool, and approval-risk
  failure modes.
- Established artifact-backed local/container quality gates across real RAG
  quality, Stage 2 evidence contracts, retrieval bakeoff, visual/table evidence,
  service smoke, deterministic security smoke, and token/cost estimate checks.
- Verified current readiness with `gate_status overall_ok=true`,
  `portfolio_readiness_check=true`,
  `stage2_contract_schema_enforced=true`, and credential-free offline tests
  passing without provider credentials; the stricter
  `interview_readiness_check` additionally requires top-tier and dependency
  security evidence.
- Added production-facing reviewer packaging: 3-minute demo storyboard,
  generated evidence artifacts, hosted-deployment readiness plan, auth/rate-limit
  and secret-handling boundaries, and a fail-closed dependency security register.
- Measured parsed-source real-lane quality under `rfp-rag-real-v6` with
  `recall@5=1.0`, `mrr=0.9922`, citation presence/validity `1.0`,
  `faithfulness=0.9369`, and `answer_relevancy=0.8109`; Stage 2 answer
  relevancy is a close-margin pass and should be discussed with its threshold
  and failure-analysis caveat.
- Documented non-adoption decisions through ADRs: vector retrieval remains the
  active baseline because BM25/hybrid did not beat it without slice
  regressions, while reranker quality evaluation is deferred until a same-set
  paid/API artifact exists.

## 60-second Interview Pitch

I built a production-adjacent Agentic RAG backend around a hard Korean document
workload: 100 public RFP HWP/PDF files. The important design choice is
source-first ingestion(원문 우선 적재): the RAG body comes from parsed source
artifacts, while CSV is only metadata. On top of that I implemented a thin
FastAPI service surface, constrained LangGraph typed-state orchestration,
guarded tools, checkpoint/HITL behavior, and artifact-backed gates for
retrieval, generation, agent stress, visual/table evidence, service smoke,
deterministic security smoke, and token/cost estimates. The repo does not ask
reviewers to trust a demo; `gate_status`, `portfolio_check`,
`production_readiness`, and credential-free tests prove whether the
local/container evidence bundle is current. I also
documented trade-offs honestly: vector remains the baseline until hybrid or
reranking wins on the same frozen set, and cloud/live-traffic evidence is
deferred rather than implied.

## Attack Questions and Answers

**Why is this senior-level rather than another RAG demo?**

Because the proof surface is operational, not just qualitative. The project has
typed agent state, conditional routing, bounded retry/reflection behavior,
checkpoint/HITL paths, tool/audit constraints, service smoke checks,
deterministic security smoke, token/cost estimate coverage, and fail-closed
evidence gates. The final claim depends on artifacts and commands, not on a
hand-picked answer.

**Why keep vector retrieval if BM25 and hybrid exist?**

The bakeoff compares vector, BM25, and hybrid RRF on the same frozen set.
BM25/hybrid are implemented and measured, but neither beats vector without
regressions on abstention/section behavior. ADR-0020 records the decision:
keep vector until a candidate wins without quality, latency, or cost regression.

**Why is reranker deferred?**

The interface exists, but there is no honest same-set quality-win artifact yet.
The real OpenAI reranker attempt was blocked by `insufficient_quota`, and the
open-provider attempt used a non-comparable query set. I would rather mark that
as deferred than overclaim.

**What does the agent add beyond plain RAG?**

The agent lane proves route/retrieve/grade/rewrite/generate/verify behavior,
metadata-tool use, abstention, bounded loops, audit records, checkpointer close
paths, HITL approve/reject convergence, audit-argument redaction, and ops-tool
budget constraints. It is intentionally evaluated through deterministic replays
and artifacts so the behavior is inspectable. I do not claim full checkpoint
state redaction or agent-level tool-call budgeting yet.

**What is not proven yet?**

The repo does not claim public cloud deployment, auth/session/rate-limit
operation, live production traffic SLOs, provider billing telemetry, or a public
dashboard. Those are separate product, credential, and disclosure decisions. The
current claim is local/containerized portfolio evidence with passing gates.

**What dependency risk remains?**

`langchain` is absent or patched in the lockfile, unused vulnerable `diskcache`
is excluded, and `ragas` `GHSA-95ww-475f-pr4f` is resolved by ADR-0021. The
judge now uses a repo-local LLM rubric instead of carrying the unpatched
package; future paid real-lane reruns should treat judge score distributions as
new calibration evidence.
