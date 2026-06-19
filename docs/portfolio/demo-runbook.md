# Senior AI Agent Engineer Portfolio Demo Runbook

This runbook is the reviewer-facing demo path for the RFP Agentic RAG system.
It shows production engineering evidence without exposing raw RFP text, secrets,
or provider credentials.

## Demo Goal

In 3-5 minutes, prove that this is not a notebook RAG demo. The live track only
checks freshness and opens curated evidence; deeper regeneration commands are a
separate track.

- source-first Korean HWP/PDF ingestion for 100 RFP documents;
- citation-grounded RAG with real-lane quality evidence;
- LangGraph agent orchestration with checkpoint/HITL and bounded tool behavior;
- FastAPI/Pydantic/SSE service surface;
- artifact-backed evaluation, deterministic security smoke, ops, and
  token/cost-estimate gates.

## Safety Rules

- Do not show `.env`, API keys, raw prompts, raw provider responses, checkpoint
  databases, or full private/raw RFP text.
- Prefer redacted artifact summaries, document IDs, metrics, and citations.
- Use local artifacts as evidence. Cloud deployment and public dashboard are
  explicitly deferred scopes.
- Do not claim a reranker quality win. ADR-0020 keeps vector until a same-set
  reranker artifact wins without regressions.
- For screen sharing, show answer summaries, citation ids, gate booleans, and
  metric tables. Do not scroll raw `source_texts`, full prediction JSONL bodies,
  checkpoint SQLite rows, or raw RFP pages.

## Pre-demo Verification

Run these immediately before recording or presenting:

```bash
python3 -m rfp_rag.gate_status
python3 -m rfp_rag.portfolio_check --out artifacts/portfolio_readiness.json
uv run python -m pytest -m "not real" -q
```

If you need the exact `python3 -m pytest` command shape, put the repo virtual
environment first on PATH:

```bash
PATH="$PWD/.venv/bin:$PATH" python3 -m pytest -m "not real" -q
```

Expected evidence:

- `gate_status`: `overall_ok=true`.
- `portfolio_readiness.json`: `portfolio_readiness_check=true`,
  `local_evidence_bundle_check=true`, `second_stage_readiness.complete=true`,
  `stage2_contract_schema_enforced=true`, `failed=[]`.
- pytest: credential-free offline tests pass without `OPENAI_API_KEY`.

If any of these fail, stop the portfolio-readiness claim and say which artifact
is stale or incomplete. Do not use older v5/v6 transition notes as current
evidence.

## 3-5 Minute Live Track

1. Open `README.md` and state the one-line project:
   production-adjacent Agentic RAG backend for 100 Korean public RFP HWP/PDF
   documents, verified through local/container evidence.
2. Open `docs/architecture/system-architecture.md` and show the flow:
   source parsing -> chunk/index -> retrieval -> LangGraph agent/service ->
   evaluation/guardrail/ops artifacts.
3. Run or show `python3 -m rfp_rag.gate_status`.
   Emphasize stale contract/source-lineage artifacts fail closed.
4. Show `artifacts/portfolio_readiness.json`.
   Point to the final readiness booleans and Stage 2 contract enforcement.
5. Show the real and Stage 2 quality metrics:
   `artifacts/eval_real/metrics.json` and
   `artifacts/eval_stage2_real/metrics.json`.
   Cite `recall@5=1.0`, citation presence/validity `1.0`, and real
   faithfulness/answer relevancy above the documented thresholds. State that
   Stage 2 answer relevancy is a close-margin pass, not a broad quality victory.
6. Show LangGraph/agent evidence:
   `artifacts/eval_agent_stress/metrics.json`.
   Mention deterministic replays for direct RAG, rewrite recovery, abstention,
   metadata-tool route, HITL approve/reject, checkpointer close path,
   audit-argument redaction, and ops-tool budget behavior.
7. Show service/security/cost evidence:
   `artifacts/service_ops/summary.json`,
   `artifacts/security_redteam/summary.json`,
   `artifacts/cost_budget/summary.json`.
8. Close with the limitation statement:
   local/container demo evidence is complete; cloud deployment, public
   dashboard, live traffic SLOs, and reranker quality-win evidence are deferred
   scopes, not hidden claims.

## Citation Trace Example

Use this when the reviewer asks whether citations are inspectable rather than
just counted:

1. Open one judged prediction from `artifacts/eval_real/predictions.jsonl` or
   `artifacts/eval_stage2_real/predictions_judged_partial.jsonl`.
2. Show only the question id, answer summary, `citations`, and chunk/document
   ids. Do not scroll raw source text.
3. Match the citation id to `artifacts/index_real/chunks.jsonl` metadata or the
   parsed-document id in `artifacts/parsed_docs/manifest.jsonl`.
4. Explain that `citation_presence` and `citation_validity` are gates over this
   mapping, not manual screenshots.

## 90-second Failure Track

Use this to show fail-closed behavior:

```bash
uv run python -m rfp_rag.guardrail_eval \
  --cases tests/fixtures/guardrail_cases.jsonl \
  --out artifacts/guardrails/summary.json
uv run python -m rfp_rag.portfolio_check --out artifacts/portfolio_readiness.json
```

Point to `failed=[]` only when it is empty. If any gate writes a failure, the
portfolio claim closes until the artifact is regenerated or the underlying
issue is fixed.

## Deep Evidence Regeneration

```bash
uv run python -m rfp_rag.stage2_service_ops
uv run python -m rfp_rag.security_redteam
uv run python -m rfp_rag.agent_stress
uv run python -m rfp_rag.retrieval_bakeoff
uv run python -m rfp_rag.cost_budget
```

Use these commands when a reviewer asks how the evidence is regenerated. They
are local artifact checks and do not require provider credentials. They are not
part of the 3-5 minute live track.

## Reviewer Questions To Invite

- Why does the system keep vector retrieval instead of adopting hybrid?
- How does `gate_status` prevent stale evidence from looking green?
- What exactly does the LangGraph agent prove beyond plain RAG?
- Which parts are production-like evidence, and which parts are deferred
  product scope?

## Top-tier Next Demo Target

The next portfolio level is tracked in `docs/portfolio/top-tier-roadmap.md` and
`artifacts/portfolio_readiness.json` under `top_tier_readiness`. The current
runbook is sufficient for repo/demo review; the top-tier demo must additionally
provide either an approved hosted reviewer URL or a one-command local reviewer
mode, independent Stage 3 holdout evidence, real observability exports, upgraded
agent orchestration evidence, deeper security/reliability reports, and the
senior case study.

Current one-command local smoke:

```bash
uv run python -m rfp_rag.top_tier_demo
uv run python -m rfp_rag.observability_report
uv run python -m rfp_rag.agent_orchestration
uv run python -m rfp_rag.security_reliability
```

Expected current state: `artifacts/top_tier_demo/summary.json` has
`top_tier_demo_complete=true`; observability and security/reliability artifacts
are redacted local evidence; orchestration evidence records a planner-executor
scenario matrix over the typed LangGraph workflow. `top_tier_readiness.complete`
remains false until Stage 3 independent holdout is implemented.
