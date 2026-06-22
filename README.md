# Senior AI Agent Engineer Portfolio: Agentic RAG for Korean Public RFPs

Tier A AI Agent/RAG 역할에 제출하기 위한 source-first Agentic RAG backend입니다.
입찰 RFP 100건의 원본 HWP/PDF를 파싱해 RAG 본문 source of truth로 쓰고,
CSV는 사업명, 발주기관, 예산, 마감일, 파일명 metadata registry로만
사용합니다. 이 레포의 주장은 public hosted service가 아니라
local/container 환경에서 재현 가능한 운영형 증거입니다: FastAPI/Pydantic
thin service, constrained LangGraph workflow, checkpoint/HITL, guarded tools,
citation-grounded generation, evaluation gates, deterministic security smoke,
local ops summary, deterministic token/cost estimates.

## Portfolio Status

Current public claim:

- **What is proven:** senior AI Agent Engineer repo/demo review에 제출 가능한
  local/container evidence bundle plus production-facing readiness artifacts.
  `gate_status`, `portfolio_check`, and credential-free tests agree with the
  generated artifacts when the dependency security gate is complete.
- **What is not claimed:** hosted cloud production, auth/session/rate-limit
  운영, live-traffic SLO, public dashboard, provider billing telemetry, or a
  reranker quality win.
- **10-minute reviewer path:** start with
  `docs/portfolio/senior-reviewer-pack.md`, then open
  `docs/portfolio/reviewer-evidence-map.md`,
  `docs/portfolio/korean-one-page-case-study.md` for the Korean interview
  summary, `docs/portfolio/company-fit-matrix.md` for role-specific positioning,
  `docs/portfolio/demo-runbook.md` for the screen-share flow, and
  `docs/portfolio/case-study.md` for deeper interview defense. This path is
  designed for Korean senior AI Agent Engineer review: architecture, RAG
  quality, LangGraph orchestration, FastAPI/SSE service evidence, observability,
  security, dependency hygiene, role fit, and explicit non-claims.
- **How to verify in 5 minutes:**

```bash
python3 -m rfp_rag.gate_status
python3 -m rfp_rag.stage2_quality_scorecard --out artifacts/stage2_quality_scorecard/summary.json
python3 -m rfp_rag.agent_orchestration
python3 -m rfp_rag.stage3_agent_scorecard --out artifacts/stage3_agent_scorecard/summary.json
python3 -m rfp_rag.production_readiness
python3 -m rfp_rag.stage4_ops_risk_scorecard --out artifacts/stage4_ops_risk_scorecard/summary.json
python3 -m rfp_rag.portfolio_check --out artifacts/portfolio_readiness.json
uv run python -m pytest -m "not real" -q
# Equivalent after putting the repo venv first on PATH:
# PATH="$PWD/.venv/bin:$PATH" python3 -m pytest -m "not real" -q
```

Latest checked evidence:

| claim | artifact / command | current evidence |
|---|---|---|
| Gate freshness | `python3 -m rfp_rag.gate_status` | `overall_ok=true`; offline, real, agent, and visual candidate lanes pass |
| Portfolio readiness | `artifacts/portfolio_readiness.json` | `portfolio_readiness_check=true`, `local_evidence_bundle_check=true`, `second_stage_readiness.complete=true`, `stage2_contract_schema_enforced=true`; `interview_readiness_check` also requires top-tier and production-facing gates |
| Real RAG quality | `artifacts/eval_real/metrics.json`; contract `rfp-rag-real-v6`; parsed-source `artifacts/index_real` | `rag_quality_complete=true`; `recall@5=1.0`, `mrr=0.9922`, `faithfulness=0.9369`, `answer_relevancy=0.8109`, citation presence/validity `1.0` |
| Stage 2 frozen evidence | `artifacts/eval_stage2_real/metrics.json`; frozen evidence-set contract | `holdout_quality_complete=true`; `recall@5=1.0`, `mrr=0.9923`, `faithfulness=0.9397`, `answer_relevancy=0.8030`, citation presence/validity `1.0`; not claimed as an independent public-traffic holdout |
| Stage 2 RAG scorecard | `artifacts/stage2_quality_scorecard/summary.json`; `docs/portfolio/stage2-rag-quality-scorecard.md` | deterministic parser/retrieval/citation/context scorecard; `context_precision_at5`, `context_recall_at5`, and `citation_precision_proxy` are computed from Stage 3 raw predictions without reintroducing Ragas |
| Agent workflow | `artifacts/eval_agent_stress/metrics.json` | constrained LangGraph workflow with deterministic replay evidence; `trajectory_pass_rate=1.0`, checkpoint/HITL/thread isolation/checkpointer close/audit-argument redaction checks pass |
| Stage 3 agent scorecard | `artifacts/stage3_agent_scorecard/summary.json`; `docs/portfolio/stage3-agent-workflow-scorecard.md` | deterministic scorecard for routing/tool accuracy, rewrite recovery, HITL approve/reject, checkpoint/thread isolation, planner-executor scenario evidence, and audit surface |
| Retrieval bakeoff | `artifacts/retrieval_bakeoff/summary.json` | vector, BM25, and hybrid RRF compared on the same frozen set; decision is `keep_vector_until_candidate_wins`; `failed=[]` |
| Visual/table evidence | `artifacts/visual_quality/summary.json` | `visual_question_count=30`, `visual_evidence_hit_rate=0.92`, unsupported visual claim rate within gate |
| Security/ops/cost | `artifacts/security_redteam/summary.json`, `artifacts/service_ops/summary.json`, `artifacts/cost_budget/summary.json` | deterministic prompt-injection/secrets/tool-policy smoke checks pass; thin FastAPI/SSE local smoke passes; deterministic token/cost estimate coverage is `1.0` for persisted real/open predictions, not provider billing telemetry |
| Stage 4 ops/risk scorecard | `artifacts/stage4_ops_risk_scorecard/summary.json`; `docs/portfolio/stage4-ops-risk-scorecard.md` | deterministic scorecard for traces, failed-run analysis, latency/token/cost evidence, service smoke, red-team checks, cost budget, dependency security, and deployment boundaries |
| Production-facing package | `docs/portfolio/reviewer-evidence-map.md`, `docs/portfolio/korean-one-page-case-study.md`, `docs/portfolio/tool-contract-matrix.md`, `artifacts/deployment_readiness/summary.json`, `artifacts/interview_demo_package/summary.json`, `artifacts/security_alerts/summary.json` | 10-minute reviewer evidence map, Korean 1-page case study, tool contract matrix, hosted-deployment readiness plan, 3-minute reviewer storyboard, and dependency security register pass; `ragas` was removed by ADR-0021 |
| Credential-free regression | `uv run python -m pytest -m "not real" -q`; equivalent venv-path `python3 -m pytest -m "not real" -q` | rerun before citing; this command must pass with no provider credentials |

Explicit limitations:

- `reranker` is implemented as an interface, but no quality-win claim is made
  until a same-set paid/API reranker artifact exists. The current ADR-0020
  decision keeps vector because BM25/hybrid do not beat it without regressions.
- `cloud_deployment` and `public_dashboard` are deferred product scopes that
  require separate credentials, spend, and public-disclosure decisions.
- No live-traffic production SLO is claimed. Current ops evidence is
  local/container demo evidence plus deterministic artifact gates.

## Gate Semantics

Offline lane (`--provider offline`) is a credential-free regression/scaffold
gate. Semantic quality is claimed only through parsed-source real artifacts and
Stage 2 frozen-evidence artifacts. Portfolio readiness is gate-based, not a single
aggregate score: the repo is ready only when `gate_status`, `portfolio_check`,
and credential-free tests all agree with the generated evidence.

## Final portfolio contract

The final portfolio target is recorded in
`docs/portfolio/2026-rfp-rag-final-goal.md`. The adversarial readiness review is
recorded in `docs/portfolio/2026-rfp-rag-adversarial-review.md`. The current
implemented architecture map is recorded in
`docs/architecture/system-architecture.md`. The Korean 1-page reviewer summary is
`docs/portfolio/korean-one-page-case-study.md`. The senior reviewer entry point is
`docs/portfolio/senior-reviewer-pack.md`, the role-fit matrix is
`docs/portfolio/company-fit-matrix.md`, the reviewer demo path is
`docs/portfolio/demo-runbook.md`, the next top-tier roadmap is
`docs/portfolio/top-tier-roadmap.md`, and resume/interview wording is
`docs/portfolio/resume-interview-bullets.md`. The project should be framed as a
production-adjacent Agentic RAG backend for an AI Agent Engineer senior portfolio,
using Korean public RFP intelligence as the hard workload: complex-document
parsing, retrieval quality evaluation, citation-grounded generation, typed
agent workflow, service/tool operation, guardrails, observability, and
evidence-inspectable RAG/Agent backends, not as a generic RFP chatbot.

The quality contract is source-first:

- 100 original Korean public RFP HWP/PDF documents are the RAG body source of
  truth.
- CSV is a metadata registry only.
- Offline artifacts prove deterministic plumbing and regression safety.
- Current `rfp-rag-real-v6` artifacts are parsed-source semantic evidence with
  cross-document hard floors and model/prompt lineage. Older v5 artifacts are
  historical only and must not be cited as current evidence.
- Agent artifacts prove constrained routing, retrieval, rewrite, metadata-tool,
  abstention, loop termination, audit coverage, checkpoint/HITL behavior,
  checkpointer close, and audit-argument redaction through deterministic
  replays and tests. Agent-level tool-call budgeting is not claimed; tool-call
  budget enforcement is covered by the read-only ops tool server.
- Agent-team operation is bounded by ADR-0013: task를 disjoint write set으로
  분해해 병렬 writer를 허용하고, main integrator가 최종 검증/통합한다.

Adversarial roadmap lock:

1. Harden `gate_status` so stale or lineage-mismatched artifacts do not look
   portfolio-ready. The command exits non-zero when any lane has stale
   contract, source-lineage, query-count, retrieval/reranker, or reaggregation
   evidence.
2. Continue benchmark hardening beyond the current 100-document metadata,
   30 hard-negative, 30 section-labeled, 20 cross-document, 25 reviewed
   visual/table, and 30 paraphrase questions before claiming retrieval or
   reranker wins.
3. Keep real-gate reruns explicit because they are cost-bearing.
4. Keep improving evidence surfaces that show answers, citations, chunks,
   source previews, gate freshness, failures, latency, and token/cost estimates.
5. Keep agent and visual claims subordinate to retrieval quality and evidence
   inspectability, while making the agent-engineering proof explicit through
   LangGraph state, conditional routing, retry/reflection limits,
   checkpoint/HITL behavior, guarded tools, traces, and failure analysis.

## Commands

```bash
python3 -m pytest
python3 -m rfp_rag.inspect_corpus --data data/data_list.csv --files data/files --out artifacts/corpus_manifest.json
python3 -m rfp_rag.parse_sources --data data/data_list.csv --files data/files --out artifacts/parsed_docs
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index --chunk-size 500 --chunk-overlap 80 --embedding-provider offline --parse-manifest artifacts/parsed_docs/manifest.jsonl
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index --out artifacts/eval --provider offline --top-k 5 --min-score 0.34 --visual-records artifacts/visual_structure_reviewed/records.jsonl
python3 -m rfp_rag.report_check --eval artifacts/eval --readme README.md
python3 -m rfp_rag.gate_status
```

`gate_status` is stricter than `report_check`: it reads the local gate artifacts
and fails stale portfolio evidence. Current local artifacts pass the offline,
real, agent, and visual candidate lanes. Rerun it before citing any current
claim; stale contract, source-lineage, query-count, retrieval/reranker, or
reaggregation evidence fails closed.

Final evidence bundle check:

```bash
python3 -m rfp_rag.portfolio_check --out artifacts/portfolio_readiness.json
```

This check verifies local gate status, guardrail regression, Docker/CI build
evidence, architecture evidence, ADR links, and Stage 2 readiness. Current
local evidence passes the local/container portfolio contract; rerun this
command before citing the repo because stale artifacts fail closed. A green
portfolio check does not claim hosted production operation, provider billing
telemetry, or public-dashboard readiness.

The same report now includes `top_tier_readiness` for the next portfolio level:
one-command reviewer demo, Stage 3 independent holdout, real observability,
upgraded agent orchestration, deeper security/reliability evidence, and a senior
case study. The CLI also reports `interview_readiness_check`, which is stricter
than `portfolio_readiness_check` and requires top-tier plus production-facing
evidence. Local top-tier evidence can pass while hosted production, public
dashboard, and live-traffic SLO claims stay out of scope.

Top-tier one-command demo smoke:

```bash
uv run python -m rfp_rag.top_tier_demo
```

This writes `artifacts/top_tier_demo/summary.json` and proves the reviewer can
exercise the local service/gate surfaces without credentials.

Production-facing interview package:

```bash
uv run python -m rfp_rag.production_readiness
```

This writes `docs/portfolio/hosted-deployment-plan.md`,
`docs/portfolio/demo-storyboard.md`, `docs/evidence/demo-package/*.md`,
`artifacts/deployment_readiness/summary.json`,
`artifacts/interview_demo_package/summary.json`, and
`artifacts/security_alerts/summary.json`.

It is fail-closed while an unpatched dependency alert is unresolved without an
explicit owner decision. Current status: `ragas` `GHSA-95ww-475f-pr4f` is
resolved by ADR-0021, which removes `ragas` from the runtime dependency graph
and uses a repo-local LLM judge.

Top-tier observability and security/reliability artifacts:

```bash
uv run python -m rfp_rag.observability_report
uv run python -m rfp_rag.agent_orchestration
uv run python -m rfp_rag.security_reliability
uv run python -m rfp_rag.stage3_holdout
```

These write redacted trace/failure-analysis artifacts, planner-executor
orchestration evidence, and a 20-case security/reliability deepening suite.
They reuse local evidence and do not call external telemetry or model providers.
`stage3_holdout` is fail-closed unless an independent cases file, matching
`eval_set_hash`, and real metrics artifact exist.

Current Stage 3 real holdout evidence:

- `stage3_holdout_quality_complete=true`;
- `eval_set_hash=ae37981b905142a5a71f4d455015ee565d705b41f21580d33eacac95ccfe7a4f`;
- `document_count=20`, `query_count=100`;
- `recall@5=1.0`, `mrr=1.0`, `citation_validity=1.0`;
- `faithfulness=0.9887`, `answer_relevancy=0.8797`;
- `unsupported_visual_claim_rate=0.0`, `abstention_precision=1.0`.

Stage 3 cost-bearing execution is listed in the paid/API plan:

```bash
uv run python -m rfp_rag.paid_lane_plan
```

The plan does not execute paid/API work. It records the Stage 3 case-freeze,
fixed-case real evaluation runner, and finalization steps so the remaining
top-tier gate cannot be hidden behind an ambiguous TODO.
The case-freeze step uses `uv run python -m rfp_rag.stage3_case_builder` to
write a deterministic 100-query Stage 3 split and contamination notes before
the real-provider run.

Stage 2 contract scaffold:

```bash
python3 -m rfp_rag.stage2_scaffold
```

This writes the expected Stage 2 artifact paths and computes current offline
eval-set coverage from `artifacts/eval/*.jsonl`. Current local evidence has
measured-pass artifacts for eval-set coverage, real frozen evidence, agent stress,
retrieval bakeoff, visual quality, service ops, deterministic security smoke, and cost
budget.

Stage 2 service ops smoke:

```bash
uv run python -m rfp_rag.stage2_service_ops
```

This records endpoint/schema/path-safety/token-cost observability evidence in
`artifacts/service_ops/summary.json`. Portfolio readiness now requires the full
offline answer path and full gate-status path:

```bash
uv run python -m rfp_rag.stage2_service_ops --full-answer --full-gates
```

The lightweight default remains useful for quick local endpoint debugging, but
it is API-shape evidence only and should not be cited as the current service
ops portfolio artifact.

Stage 2 deterministic security smoke:

```bash
uv run python -m rfp_rag.security_redteam
```

This writes `artifacts/security_redteam/summary.json` plus publishability and
retention notes. It is a deterministic security smoke/redaction gate: it checks
prompt-injection/secrets blocking, malicious document/retrieved-evidence/tool
output fixture cases, tool allowlist and tool-budget enforcement, audit
redaction, and selected demo-visible artifact leak scans. It is not a full adversarial
security assessment of a hosted service.

Stage 2 agent stress:

```bash
uv run python -m rfp_rag.agent_stress
```

This writes `artifacts/eval_agent_stress/metrics.json` and
`artifacts/eval_agent_stress/replay.jsonl` from deterministic LangGraph
replays covering direct RAG, rewrite recovery, abstention, metadata-tool route,
HITL approve/reject, thread reuse isolation, checkpointer close path,
audit-argument redaction, and ops-tool budget behavior.

Stage 2 cost budget:

```bash
uv run python -m rfp_rag.cost_budget
```

This writes `artifacts/cost_budget/summary.json` from persisted real/open
prediction artifacts. It records deterministic token and cost estimates for
budget regression gating, including optional `eval_open_rerank`,
`eval_real_rerank`, and `eval_stage2_real` prediction artifacts when they
exist; it does not claim to be provider billing data. If a lane has no persisted
predictions, its provider billing and per-request token telemetry are not
claimed.

Paid/API lane dry-run plan:

```bash
uv run python -m rfp_rag.paid_lane_plan
```

This writes `artifacts/paid_lane_plan/summary.json` without executing any
provider calls. It records the exact cost-bearing commands, required environment
variable names, expected artifact writes, current cost-budget estimate, and the
post-run verification commands. Use it as the approval checklist before running
`real_openai`, Stage 2 real frozen-evidence, or same-set LLM reranker lanes.

Stage 2 real frozen-evidence finalize:

```bash
uv run python -m rfp_rag.stage2_real
```

This converts the persisted `artifacts/eval_stage2_real/metrics.json` output
from an approved `real_openai` frozen-evidence run into the Stage 2 portfolio contract.
It is fail-closed: without real lineage, valid evaluation status, and the
required Stage 2 quality floors, the artifact remains
`holdout_quality_complete=false`. It does not call the provider or generate
answers; it only validates and normalizes the already generated metrics.

Stage 2 retrieval bakeoff:

```bash
uv run python -m rfp_rag.retrieval_bakeoff
```

This writes `artifacts/retrieval_bakeoff/summary.json`. Current local vector,
BM25, and hybrid RRF runs are measured on the 545-query offline set and share
the same comparison hash. The bakeoff passes with the decision
`keep_vector_until_candidate_wins`: BM25 and hybrid are implemented and
measured, but neither beats vector without regressions. Reranker remains an
optional/deferred paid/API quality claim until a same-set `reranker="llm"`
artifact exists. The decision record is `docs/adr/0020-retrieval-bakeoff.md`.

Stage 2 RAG quality scorecard:

```bash
uv run python -m rfp_rag.stage2_quality_scorecard
```

This writes `artifacts/stage2_quality_scorecard/summary.json` and aggregates
parser quality, retrieval bakeoff, visual/table quality, Stage 2 frozen real
evidence, Stage 3 holdout quality, and deterministic Stage 3 prediction-derived
context metrics. It is credential-free and does not reintroduce Ragas.

Stage 2 visual quality:

```bash
uv run python -m rfp_rag.visual_quality
```

This writes `artifacts/visual_quality/summary.json` from current visual/table
eval metrics, visual candidate eval results, and sidecar regression evidence.
Current local visual quality is measured-pass: 30 visual/table questions,
`visual_evidence_hit_rate=0.92`, `unsupported_visual_claim_rate=0.0353`, and
sidecar citation/abstention no-regression both pass.

## FastAPI service surface

The service layer is intentionally thin: it exposes the existing source-first
RAG chain and local gate evidence without changing eval semantics.

```bash
uv run uvicorn rfp_rag.service.app:app --host 127.0.0.1 --port 8000
```

Endpoints:

- `GET /healthz`: service readiness.
- `POST /v1/answer`: typed Pydantic request/response wrapper around
  `answer_query`.
- `POST /v1/answer/stream`: SSE stream with `status` and `final` events.
- `GET /v1/gates`: local `gate_status` payload for portfolio evidence
  freshness.
- `GET /v1/ops/summary`: local observability summary for prediction warnings,
  answer errors, estimated tokens/cost, and agent tool-call outcomes.

The answer endpoints run a basic prompt-injection/secrets guardrail before
retrieval. Requests that try to override instructions or extract credentials are
blocked with `400 guardrail_blocked`; this is a first service-level tripwire,
not a full red-team suite.

Service inputs are intentionally narrow: `/v1/answer` only allows the offline
provider and the approved local `artifacts/index` path, while ops/gate endpoints
reject paths that escape the repository artifact boundary. Cost-bearing real
lanes stay outside the service surface unless a separate approval/auth path is
designed.

Run deterministic guardrail regression:

```bash
python3 -m rfp_rag.guardrail_eval \
  --cases tests/fixtures/guardrail_cases.jsonl \
  --out artifacts/guardrails/summary.json
```

The current fixture covers prompt-injection, secret-exfiltration, and benign RFP
questions. Local evidence currently passes all 7 cases with block recall,
allow recall, and category exact match at `1.0`.

Offline example:

```bash
curl -s http://127.0.0.1:8000/v1/answer \
  -H 'content-type: application/json' \
  -d '{"question":"한영대학교 트랙운영 학사정보시스템 고도화 사업을 요약해줘","index_dir":"artifacts/index","provider":"offline","top_k":5,"min_score":0.34}'
```

Ops summary example:

```bash
curl -s 'http://127.0.0.1:8000/v1/ops/summary?eval_dir=artifacts/eval&audit_path=artifacts/eval_agent/agent_artifacts/audit.jsonl'
```

## MCP-style ops tool server

ADR-0016 records the narrow MCP-style ops tool decision. This is an
MCP-inspired JSONL shim, not a full MCP server/transport/auth implementation.
The server is dependency-free and JSONL-based so it can run in CI/local shells
without background daemon, auth, or storage decisions. It exposes read-only
local tools with explicit allowlist, path validation, schema validation, and
max tool-call budget guardrails:

- `gate.status`: read `python3 -m rfp_rag.gate_status` equivalent evidence.
- `ops.summary`: summarize eval predictions and agent audit logs.
- `eval.metrics`: read a local `metrics.json` artifact.

Allowed workflows: pre-demo gate checks, ops/audit summaries, and local metrics
inspection under `artifacts/`. Forbidden workflows: `real_openai` execution,
artifact mutation, arbitrary file reads, arbitrary SQL, credential access, and
background daemon operation.

Example:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"ops.summary","arguments":{"eval_dir":"artifacts/eval","audit_path":"artifacts/eval_agent/agent_artifacts/audit.jsonl"}}}' \
  | python3 -m rfp_rag.ops_tool_server --max-tool-calls 3
```

Restrict a session to a single tool:

```bash
python3 -m rfp_rag.ops_tool_server --allow-tool gate.status --max-tool-calls 1
```

## Docker and CI

ADR-0015 records the Docker/CI baseline. The container image intentionally
contains only the FastAPI app and locked Python dependencies. It does not bake
in local `data/`, `artifacts/`, `.env`, or raw RFP files; mount those directories
read-only when running answer or gate endpoints.

```bash
docker build -t rfp-rag-service .
docker run --rm -p 8000:8000 rfp-rag-service
```

With local evidence mounted:

```bash
docker run --rm -p 8000:8000 \
  -v "$PWD/artifacts:/app/artifacts:ro" \
  -v "$PWD/data:/app/data:ro" \
  rfp-rag-service
```

GitHub Actions runs credential-free PR/push regression checks:

```bash
uv sync --frozen --group dev
uv run ruff format --check rfp_rag tests
uv run ruff check rfp_rag tests
uv run pytest -m "not real"
docker build -t rfp-rag-service:ci .
```

Because `data/` is intentionally gitignored, CI creates a private-data-free
synthetic 100-row corpus before running tests. Local quality claims still come
from the real `data/` and `artifacts/` evidence described in the gate sections.
The CI Docker build proves the service image can be assembled independently of a
local Docker Desktop daemon.

## Source parsing lane

The RAG path is source-first. `data_list.csv` remains the metadata registry, and
source parsing extracts original HWP/PDF text before indexing.

```bash
python3 -m rfp_rag.parse_sources --data data/data_list.csv --files data/files --out artifacts/parsed_docs
```

Outputs:

- `artifacts/parsed_docs/manifest.jsonl`
- `artifacts/parsed_docs/summary.json`
- `artifacts/parsed_docs/text/*.txt` for parsed documents
- `artifacts/parsed_docs/pdf/*.pdf` for page-citation evidence
- `artifacts/parsed_docs/page_text/*.jsonl` for extracted per-page text

For `.hwp` files, the source parser uses a measured failover chain:
`unhwp -> hwp5txt -> converted_pdf_pymupdf`. The manifest records the selected
`parser_backend`, `content_source`, `source_quality`, and `text_backend_attempts`
for each document. There is no CSV text fallback: if source parsing cannot
produce text, indexing fails instead of silently using the metadata CSV text.
LibreOffice HWP-to-PDF conversion plus PyMuPDF page text remains the page-level
citation evidence path.
Native `.pdf` files are parsed directly with PyMuPDF for source text and copied
as source-PDF citation evidence. Use `--no-page-citation` to skip this evidence
pass in constrained local checks.

## Parser/render bakeoff

Before parsed HWP output becomes an index source, the project compares parser and
renderer backends on representative RFP samples.

```bash
python3 -m rfp_rag.run_parser_bakeoff \
  --data data/data_list.csv \
  --files data/files \
  --parse-manifest artifacts/parsed_docs/manifest.jsonl \
  --out artifacts/parser_bakeoff
```

Outputs:

- `artifacts/parser_bakeoff/samples.json`
- `artifacts/parser_bakeoff/results.jsonl`
- `artifacts/parser_bakeoff/summary.json`

Optional backends such as `rhwp`, `unhwp`, `hwpxkit`, and LibreOffice are recorded
as `missing_dependency` when unavailable, so the bakeoff remains reproducible on
a minimal local setup.

`summary.json` also records `ingestion_recommendation`. The current local rule
separates searchable text from visual evidence: prefer `unhwp` for text/JSON,
prefer `libreoffice_pdf` for rendered PDF evidence, and keep `rhwp` experimental
until its timeout/DocInfo failures are resolved.

## Parser quality evaluation

After source parsing creates text, PDF, and page-text artifacts, run deterministic
quality evaluation:

```bash
python3 -m rfp_rag.run_parser_quality_eval \
  --parsed-dir artifacts/parsed_docs \
  --out artifacts/parser_quality
```

Outputs:

- `artifacts/parser_quality/per_doc.jsonl`
- `artifacts/parser_quality/summary.json`
- `artifacts/parser_quality/risky_docs.jsonl`

The evaluator scores parsed text against PDF page text, tracks page-citation
coverage, estimates table-like line preservation, and records image/drawing
signals from PyMuPDF. Drawing-heavy pages are treated as chart candidates, not as
confirmed chart understanding; OCR/VLM judging is a later quality layer.

## Visual parsing audit

Before adding OCR/VLM parsing, select a bounded review set from parser-quality
signals:

```bash
python3 -m rfp_rag.run_visual_audit \
  --parsed-dir artifacts/parsed_docs \
  --quality-dir artifacts/parser_quality \
  --out artifacts/visual_audit \
  --max-docs 15 \
  --max-pages-per-doc 5
```

Outputs:

- `artifacts/visual_audit/summary.json`
- `artifacts/visual_audit/samples.jsonl`
- `artifacts/visual_audit/review.md`

This lane does not claim visual understanding. It ranks documents and pages with
chart/drawing/image/table-loss signals, then asks a human reviewer to label
whether the selected visual elements contain bid-review information that is not
already recoverable from extracted text.

Manual review on 2026-06-15 found repeated visual-only business information in
Gantt schedules, organization charts, system architecture diagrams, target
service models, and dashboard screenshots. The adopted next step is a targeted
page-level visual-structure extraction lane, not full OCR/VLM replacement of the
text pipeline. See
`docs/evidence/visual-audit-manual-review-2026-06-15.md` and
`docs/adr/0007-targeted-visual-structure-extraction.md`.

Create the first targeted visual-structure seed artifacts from the manual review
evidence:

```bash
python3 -m rfp_rag.run_visual_structure_extraction \
  --audit-dir artifacts/visual_audit \
  --review docs/evidence/visual-audit-manual-review-2026-06-15.md \
  --out artifacts/visual_structure
```

Outputs:

- `artifacts/visual_structure/records.jsonl`
- `artifacts/visual_structure/summary.json`
- `artifacts/visual_structure/review_queue.md`

The seed lane emits page/type records with `doc_id`, `page`, `visual_type`,
`business_fields`, `evidence_ref`, `extractor`, `confidence`, and
`review_status`. `structured_facts` intentionally starts empty until a targeted
extractor or reviewer fills facts for each queued visual record.

Reviewer facts are merged through a separate gold-set lane:

```bash
python3 -m rfp_rag.run_visual_fact_review \
  --records artifacts/visual_structure/records.jsonl \
  --facts docs/evidence/visual-structure-review-facts.seed.jsonl \
  --out artifacts/visual_structure_reviewed
```

This is the A-first path for visual facts. The reviewer fact JSONL is the gold
set for later OCR/VLM comparison: accepted facts are merged into
`structured_facts`, rejected facts become negative gold labels, and needs-review
facts remain unmerged. OCR/VLM extraction stays deferred until a candidate
extractor can be scored against this reviewer gold set.

Check whether the reviewed gold set is complete enough to trust as a comparison
baseline:

```bash
python3 -m rfp_rag.run_visual_gold_check \
  --summary artifacts/visual_structure_reviewed/summary.json
```

The default target is `resolved_record_ratio >= 0.80` with no unresolved
`needs_review` or unknown-record counts. Rejected facts count as resolved
negative labels, so a page-reviewed gold set can evaluate both recall and
precision for later OCR/VLM candidates.

Current expanded gold result: `fact_count=110`, `accepted_fact_count=25`,
`rejected_fact_count=85`, `resolved_record_ratio=1.0`,
`needs_review_fact_count=0`, and `unknown_record_count=0`. The gold set is now a
complete comparison set over the current 110 visual records, not only the
initial 60-record calibration subset.

Create the next reviewer batch for visual records that still require page review
or confirm that none remain:

```bash
python3 -m rfp_rag.run_visual_review_batch \
  --records artifacts/visual_structure/records.jsonl \
  --facts docs/evidence/visual-structure-review-facts.seed.jsonl \
  --out artifacts/visual_review_batch_next \
  --review-status needs_page_review
```

This writes `records.jsonl`, `facts_template.jsonl`, `summary.json`, and
`review_queue.md`. With the current expanded seed file, the command reports
`existing_fact_record_count=110` and `selected_record_count=0`, so there is no
remaining page-review batch for the current visual-structure records.

Evaluate a candidate extractor output against the reviewer gold set:

```bash
python3 -m rfp_rag.run_visual_gold_eval \
  --gold docs/evidence/visual-structure-review-facts.seed.jsonl \
  --candidate docs/evidence/visual-structure-candidate-facts.example.jsonl \
  --out artifacts/visual_gold_eval
```

The evaluator scores candidate facts by `(record_id, fact_type, field)` and
reports precision, recall, F1, negative-label violations, and unknown candidate
claims. The checked-in candidate file is only a smoke fixture, not an OCR/VLM
result.

Generate the deterministic no-model local baseline before adopting OCR/VLM:

```bash
python3 -m rfp_rag.run_visual_local_baseline \
  --records artifacts/visual_structure/records.jsonl \
  --out artifacts/visual_local_baseline_expanded \
  --review-status reviewed_needs_extraction \
  --review-status needs_page_review

python3 -m rfp_rag.run_visual_gold_eval \
  --gold docs/evidence/visual-structure-review-facts.seed.jsonl \
  --candidate artifacts/visual_local_baseline_expanded/candidate_facts.jsonl \
  --out artifacts/visual_local_baseline_expanded_eval
```

Current expanded local baseline result: `candidate_fact_count=110`,
`precision=0.19090909`, `recall=0.84`, `f1=0.31111111`,
`negative_violation_count=52`, and `unknown_candidate_count=37`. This is the
floor comparison group for later OCR/VLM or OCR+layout candidates, not a
production-quality visual extractor.

Generate the first local OCR candidate with Tesseract:

```bash
python3 -m rfp_rag.run_visual_tesseract_candidate \
  --records artifacts/visual_structure/records.jsonl \
  --out artifacts/visual_tesseract_candidate_expanded \
  --dpi 120 \
  --timeout-seconds 15 \
  --review-status reviewed_needs_extraction \
  --review-status needs_page_review

python3 -m rfp_rag.run_visual_gold_eval \
  --gold docs/evidence/visual-structure-review-facts.seed.jsonl \
  --candidate artifacts/visual_tesseract_candidate_expanded/candidate_facts.jsonl \
  --out artifacts/visual_tesseract_candidate_expanded_eval

python3 -m rfp_rag.run_visual_candidate_check \
  --summary artifacts/visual_tesseract_candidate_expanded_eval/summary.json \
  --out artifacts/visual_tesseract_candidate_expanded_gate
```

Current expanded precision-hardened Tesseract candidate result:
`candidate_fact_count=26`, `precision=0.76923077`, `recall=0.8`,
`f1=0.78431373`, `negative_violation_count=3`, and
`unknown_candidate_count=3`. This now clears the current visual-candidate target
on precision, recall, F1, and rejected-label violations. The gate artifact is
`artifacts/visual_tesseract_candidate_expanded_gate/summary.json`; this remains
a local OCR candidate rather than final visual understanding.

Attach gate-passing visual facts to an answer as sidecar context:

```bash
python3 -m rfp_rag.ask \
  --index artifacts/index \
  --query "제안요청서의 일정표나 요구사항표 근거를 함께 보여줘" \
  --visual-candidates artifacts/visual_tesseract_candidate_expanded/candidate_facts.jsonl \
  --visual-gate artifacts/visual_tesseract_candidate_expanded_gate/summary.json
```

The sidecar path keeps source-first boundaries intact. It checks the visual
candidate gate before loading facts, leaves retrieval ranking and indexed source
chunks unchanged, renders visual facts under `시각근거:` in the generator/judge
context, and exposes them as `sources[].visual_evidence`.

## Section-aware indexing

`build_index` detects coarse RFP sections before chunking. Each chunk carries
`section_title`, `section_type`, `section_path`, optional page fields, and
`requirement_ids`. Retrieval prepends section metadata to vector/BM25 text, and
answer sources expose section/page fields for citation review. When a query
contains the literal word `섹션` and an exact `section_title`, vector retrieval
also injects exact section-title candidates from `chunks.jsonl` before ranking,
so the offline section lookup eval is not limited by dense/lexical vector
collisions.

`evaluate` writes `section_lookup_questions.jsonl`, `paraphrase_questions.jsonl`,
and reports
`section_hit_rate`. With `--visual-records
artifacts/visual_structure_reviewed/records.jsonl`, it also writes
`visual_table_questions.jsonl` from reviewed page-level visual/table facts and
reports `visual_evidence_hit_rate`. Current offline calibration uses
`--min-score 0.34`; the section-aware score distribution is recorded in
`artifacts/eval/metrics.json` and includes injected section-candidate scores for
the section lookup subset.

### Retrieval mode

`--retrieval-mode vector` is the default. `--retrieval-mode hybrid` fuses Qdrant
vector candidates with local BM25 candidates from `chunks.jsonl` using
reciprocal-rank fusion.

```bash
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index \
  --out artifacts/eval_hybrid_offline --provider offline --top-k 5 \
  --min-score 0.34 --retrieval-mode hybrid \
  --visual-records artifacts/visual_structure_reviewed/records.jsonl
```

Hybrid retrieval is an experiment lane. It must be calibrated separately before
being treated as an offline scaffold signal; it does not replace the
`real_openai` quality gate.

Current section/visual/paraphrase-aware vector offline gate at `--min-score
0.34` over the 545-query benchmark:

| mode | queries | recall@5 | all_docs@5 | cross-doc all_docs@5 | paraphrase recall@5 | paraphrase metadata_exact | mrr | citation_validity | abstention_pass | section_hit_rate | visual_evidence_hit_rate | offline_scaffold_complete |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| vector | `545` | `0.9864` | `0.9748` | `0.4` | `1.0` | `0.8667` | `0.9841` | `0.9845` | `1.0` | `1.0` | `0.92` | `true` |

The previous hybrid smoke comparison was run on the smaller benchmark and is no
longer a same-dataset adoption signal after 100-document metadata expansion.
Keep `vector` as the offline gate mode until hybrid has its own calibrated
545-query comparison plus abstention, cross-document, section-lookup,
visual/table, and paraphrase evidence. The current vector baseline exposes two
remaining weaknesses: cross-document top-5 often fills with multiple chunks from
one expected document, and paraphrase metadata/citation exactness is lower than
the aggregate.

### Reranker

`--reranker none` is the default for both `ask` and `evaluate`. `--reranker llm`
adds a lane-compatible LLM reranker that reranks a larger candidate pool from
the existing retriever via `--rerank-candidate-k`, then returns the top-k chunks
to generation and evaluation. The implementation is intentionally limited to
`real_openai` and `open` lanes; offline evaluation rejects `--reranker llm` so
the credential-free contract remains intact.

The current decision is ADR-0008: keep `vector` and `hybrid` as controls, skip a
full deterministic reranker, and evaluate the B path through the existing
real/open provider surfaces first. Actual `--reranker llm` runs require explicit
cost/API approval.

Example shape, after approving the relevant provider cost:

```bash
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_open \
  --out artifacts/eval_open_rerank --provider open --top-k 5 --min-score 0.55 \
  --reranker llm --rerank-candidate-k 10 \
  --visual-records artifacts/visual_structure_reviewed/records.jsonl
```

## Real provider quality lane (rfp-rag-real-v6)

The contract version is bumped for code/report semantics. Regenerate
`artifacts/eval_real` before using real-lane artifacts as current evidence.

Requires `OPENAI_API_KEY`. Models default to `text-embedding-3-small` /
`gpt-5.4-mini` (generation) / `gpt-5.4-mini` (judge — §10-11 A/B 검증, ADR-0005);
override via `RFP_EMBEDDING_MODEL`, `RFP_GENERATION_MODEL`, `RFP_JUDGE_MODEL`.

```bash
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files \
  --out artifacts/index_real --chunk-size 500 --chunk-overlap 80 \
  --embedding-provider openai --parse-manifest artifacts/parsed_docs/manifest.jsonl
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_real \
  --out artifacts/eval_real --provider real_openai --top-k 5 --min-score 0.47 \
  --visual-records artifacts/visual_structure_reviewed/records.jsonl
```

- `rag_quality_complete` requires every aggregate threshold in
  `artifacts/eval_real/metrics.json` (`thresholds`), every per-type hard floor in
  `per_type_thresholds`, model/prompt lineage fields, and `evaluation_valid`
  (error rate <= 10%).
- Current checked evidence passes the v6 real gate. Rerun the command above
  only when intentionally refreshing paid/API evidence; otherwise use
  `gate_status` and `portfolio_check` to validate freshness before citing it.
- After a gate-semantics (contract) change, regenerate evidence without API calls:
  `python3 -m rfp_rag.evaluate --reaggregate --out artifacts/eval_real --provider real_openai`
  recomputes metrics/contract/report from the preserved `predictions.jsonl` and marks
  the output with `reaggregated_from_predictions: true`.
- Long-running evals write recovery/observability artifacts before final metrics:
  `eval_progress.jsonl`, `predictions_unjudged_partial.jsonl`,
  `predictions_unjudged.jsonl`, and `predictions_judged_partial.jsonl`. If the
  judge stalls or is interrupted, inspect these files before rerunning.
- For provider rate limits, throttle/retry the long real run without changing the
  contract: `RFP_EVAL_ANSWER_DELAY_SECONDS`, `RFP_EVAL_ANSWER_RETRY_ATTEMPTS`,
  `RFP_EVAL_ANSWER_RETRY_DELAY_SECONDS`, and
  `RFP_EVAL_JUDGE_START_DELAY_SECONDS`.
- Calibrate `--min-score` per lane from `score_distribution` in `metrics.json`
  (offline lane: 0.34, real lane: 0.47). Record any recalibration rationale in the
  evaluation report.
- Citation metrics compare retrieved chunks against expected docs (comparable across
  lanes); the LLM's self-reported citations (`last_cited_chunk_ids`) are diagnostic only.
- Qdrant runs in embedded local mode: single-process only. A rebuild on the same
  `--out` path recreates the Qdrant directory, so preserve old evidence by first
  using a candidate output path or by explicitly approving canonical artifact
  replacement. Production migration path is a Docker Qdrant server with the same
  client API.
- Offline lane stays credential-free: `python3 -m pytest -m "not real"` must pass
  without `OPENAI_API_KEY`.
- Full real cycle cost estimate: roughly $1 with default models (judge `gpt-5.4-mini`;
  set `RFP_JUDGE_MODEL=gpt-5.4` for the pricier reference judge, ~$5).
- Judge model A/B: 저장된 predictions에 judge만 재실행해 모델 간 점수 합치도를 비교
  (generation 재실행 없음 — judge 비용만 발생). `RFP_JUDGE_BASE_URL`/`RFP_JUDGE_API_KEY`로
  OpenAI 호환 백엔드(DeepSeek 등) judge도 같은 스크립트로 검증:
  `RFP_JUDGE_MODEL=gpt-5.4-mini PYTHONPATH=. python3 scripts/judge_ab.py
  --predictions artifacts/eval_real/predictions.jsonl --out artifacts/judge_ab`
- Assumption: the corpus is trusted public RFP documents; prompt-injection
  robustness against adversarial corpus content is out of scope for this cycle.

## Open lane — 저비용 이터레이션 (rfp-rag-open-v4)

The contract version is bumped for code/report semantics. Regenerate
`artifacts/eval_open` before using open-lane artifacts as current evidence.

오픈소스/저가 모델로 같은 평가 파이프라인을 돌리는 이터레이션 레인입니다
(채택 근거·백엔드 비교는 `docs/adr/0005-open-lane-backend-and-judge-strategy.md`).
**게이트 증거가 아닙니다** — judge 점수를 이터레이션 신호로만 쓰고,
`rag_quality_complete`는 real lane에서만 판정합니다.

- 생성 기본: DeepSeek `deepseek-v4-flash` (`DEEPSEEK_API_KEY` 필요, 60건 ~$0.05).
  `RFP_OPEN_BASE_URL=http://localhost:11434/v1` + `RFP_OPEN_MODEL=qwen3:8b`로
  로컬 Ollama 백업 전환 — OpenAI 호환 base_url 하나로 백엔드를 교체합니다.
- 임베딩 기본: 로컬 Ollama `bge-m3` (키 불필요, `ollama pull bge-m3` 선행).

```bash
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files \
  --out artifacts/index_open --chunk-size 500 --chunk-overlap 80 \
  --embedding-provider open --parse-manifest artifacts/parsed_docs/manifest.jsonl
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_open \
  --out artifacts/eval_open --provider open --top-k 5 --min-score 0.55 \
  --visual-records artifacts/visual_structure_reviewed/records.jsonl
```

`--min-score 0.55`는 첫 성공 런의 `score_distribution`에서 보정한 open lane 전용 cutoff입니다. abstention top score 최댓값은 `0.49755216`, in-domain top score 최솟값은 `0.60993228`이고, 두 분포 사이의 gap에 cutoff를 둡니다.
- open lane 평가도 judge를 실행합니다 — 기본 judge는 OpenAI `gpt-5.4-mini`이므로
  `OPENAI_API_KEY`가 필요하고, DeepSeek judge(A/B 검증 후)는 `RFP_JUDGE_BASE_URL`로
  전환합니다.

## LangGraph agent lane (rfp-agent-v2)

LangGraph `StateGraph` 기반 stateful multi-step agent: 질의 라우팅(rag/metadata) →
검색 → 충분성 판정 → 질의 재작성 루프(≤2회) → 생성 → 인용 검증 → (저장 요청 시)
human-in-the-loop 승인. 그래프 토폴로지는 레인 공통이며 Router/Rewriter 두뇌만
offline 규칙 기반 / real LLM(`gpt-5.4-mini` structured output)으로 주입됩니다.

```bash
# agent 게이트 평가 (offline 판정 — API 키 불필요)
python3 -m rfp_rag.agent.evaluate_agent --data data/data_list.csv --files data/files \
  --index artifacts/index --out artifacts/eval_agent --provider offline --top-k 5 --min-score 0.34

# 질문 1회 실행
python3 -m rfp_rag.agent.run_agent --index artifacts/index --data data/data_list.csv \
  --files data/files --question "사업 금액이 가장 큰 공고 3건은 뭐야?" --thread-id t1 --min-score 0.34

# HITL: "...보고서로 저장해줘" 질문은 interrupt로 멈춤 → 같은 thread-id로 재개
python3 -m rfp_rag.agent.run_agent --index artifacts/index --data data/data_list.csv \
  --files data/files --thread-id t1 --approve   # 또는 --reject
```

- `agent_lane_complete`는 offline 레인에서 routing/retrieval/rewrite/tool/
  abstention/loop/audit를 판정합니다. HITL/checkpoint는 구현·단위 테스트·데모로
  보조하며, 완료 품질 claim은 Stage 2 stress gate에서 별도 판정합니다.
- 도구: `search_rfp`(읽기), `aggregate_metadata`(읽기 — 금액/마감일/발주기관
  필터·정렬·건수·합계), `save_report`(쓰기 — 승인 필수, 경로 탈출 차단).
- 모든 도구 호출은 `<artifacts>/audit.jsonl`에 기록됩니다
  (`ts/thread_id/tool/redacted args/outcome/approved`). Query-like 입력은
  hash/length/safe preview로 저장하고 secret/PII-like 값은 redaction합니다.
- 상태는 `<artifacts>/checkpoints.sqlite`에 영속 — 프로세스를 종료해도 같은
  `--thread-id`로 승인 대기를 재개할 수 있습니다.

## Observability (optional Langfuse tracing)

`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`가 환경에 있으면 LangGraph 실행, LLM 생성,
repo-local LLM judge 호출이 Langfuse로 트레이싱됩니다 (`rfp_rag/tracing.py`, 채택 근거는
`docs/adr/0001-llm-observability-tool.md`). **키가 없으면 완전한 no-op** — offline lane의
credential-free 불변식에 영향이 없습니다. 키 설정은 `.env.example` 참조.

- `LANGFUSE_BASE_URL`은 선택값 (기본 Langfuse Cloud; self-host나 리전 인스턴스만 지정).
- CLI(run_agent / evaluate / evaluate_agent)는 종료 전에 트레이스를 flush하므로
  실행 직후 대시보드에서 확인할 수 있습니다 (예외로 중단돼도 flush됨).
- real lane 평가를 트레이싱하면 judge 비용이 호출·토큰 단위로 분해되어 보입니다.

## Generated artifacts

- `artifacts/corpus_manifest.json`: row/file normalization inventory.
- `artifacts/index/manifest.json`, `artifacts/index/chunks.jsonl`, `artifacts/index/qdrant/`: offline lexical-hash index (embedded Qdrant).
- `artifacts/demo_answer.json`, `artifacts/demo_abstention.json`: cited QA and abstention examples.
- `artifacts/eval/contract.json`: versioned offline report/evaluation contract.
- `artifacts/eval/metrics.json`, `artifacts/eval/predictions.jsonl`, `artifacts/eval/report.md`: offline evaluation outputs.
- `artifacts/eval/eval_progress.jsonl`, `artifacts/eval/predictions_unjudged*.jsonl`,
  `artifacts/eval/predictions_judged_partial.jsonl`: long-running eval recovery
  and progress artifacts.
