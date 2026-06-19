# Top-tier Korean Senior AI Agent Engineer Portfolio Roadmap

This roadmap raises the RFP Agentic RAG repo from a strong local evidence
portfolio to a top-tier senior AI Agent Engineer portfolio. The target reviewer
reaction is: this is not a notebook demo; this is a complex-document AI system
with product workflow, agent orchestration, evaluation, observability, security,
and honest operational boundaries.

## Market Signal

Korean AI Agent/RAG job postings repeatedly ask for:

- LangChain/LangGraph or similar agent orchestration frameworks;
- RAG, vector/graph retrieval, tool calling, and prompt/context engineering;
- evaluation, tracing, debugging, and quality improvement loops;
- Python API backends, Docker, CI/CD, cloud or Kubernetes operation;
- workflow automation that can be used by a real organization, not only a demo.

The portfolio should therefore sell one sharp story: Korean public RFP
intelligence is the hard workload, and the system proves that the engineer can
build, evaluate, operate, and defend an Agentic RAG platform around that
workload.

## Final Claim

Final claim:

> Production-adjacent Agentic RAG platform for Korean public RFP intelligence,
> verified by a reviewer-facing demo, independent holdout evaluation, real
> observability artifacts, upgraded agent orchestration evidence, and a senior
> case study.

Non-claims:

- hosted production with live traffic SLOs unless deployment evidence exists;
- public multi-tenant SaaS readiness;
- reranker quality win unless same-set evidence beats vector without
  regressions;
- full security assessment of an internet-facing service.

## Phase 1: Hosted or one-command reviewer demo

Goal: a reviewer can verify the system without reading long setup notes.

Required evidence:

- `artifacts/top_tier_demo/summary.json`;
- `top_tier_demo_complete=true`;
- one clear `reviewer_command` or approved public demo URL;
- no provider credentials required for demo mode;
- `/healthz`, answer, streaming, gate summary, and ops summary surfaces shown;
- first verified answer and citation trace within 5 minutes.

Gate metrics:

| metric | target |
|---|---:|
| `one_command_demo_pass` | `1.0` |
| `no_credentials_required` | `1.0` |
| `streaming_demo_pass` | `1.0` |
| `gate_summary_demo_pass` | `1.0` |
| `time_to_first_verified_answer_sec` | `<= 300` |

Stop condition: public deployment, cloud credentials, or externally accessible
URLs require explicit user approval before execution.

## Phase 2: Stage 3 independent holdout

Goal: move beyond the current frozen Stage 2 evidence-set claim. Stage 3 must
use a separately documented corpus/query split that was not used for tuning.

Required evidence:

- `artifacts/eval_stage3_holdout/metrics.json`;
- `stage3_holdout_quality_complete=true`;
- `corpus_split_manifest_path`, `label_rubric_path`, and `eval_set_hash`;
- query-set counts by slice;
- judged real-lane metrics and failure list.

Gate metrics:

| metric | target |
|---|---:|
| `document_count` | `>= 20` |
| `query_count` | `>= 100` |
| `recall@5` | `>= 0.90` |
| `mrr` | `>= 0.80` |
| `citation_validity` | `>= 0.95` |
| `faithfulness` | `>= 0.85` |
| `answer_relevancy` | `>= 0.78` |
| `unsupported_visual_claim_rate` | `<= 0.05` |
| `abstention_precision` | `>= 0.90` |

Stop condition: paid real-provider evaluation requires explicit approval and a
cost estimate before execution.

## Phase 3: Real observability

Goal: show that failures, latency, cost, traces, and tool behavior are inspectable.

Required evidence:

- `artifacts/observability/summary.json`;
- trace provider choice and trace export path;
- latency p50/p95, token/cost, and tool success/failure summaries;
- failed-run analysis document with at least five classified failures.

Gate metrics:

| metric | target |
|---|---:|
| `trace_export_present` | `1.0` |
| `latency_p50_ms_recorded` | `1.0` |
| `latency_p95_ms_recorded` | `1.0` |
| `token_cost_recorded` | `1.0` |
| `tool_success_rate_recorded` | `1.0` |
| `failed_run_analysis_count` | `>= 5` |

Stop condition: telemetry services must have storage location, retention,
project/user scope, and redaction policy before adoption.

## Phase 4: Upgraded agent orchestration

Goal: prove agent engineering beyond a single RAG chain.

Target pattern: planner-executor or supervisor-worker, implemented only where
the business workflow naturally decomposes.

Required evidence:

- `artifacts/agent_orchestration/summary.json`;
- scenario matrix for direct answer, multi-tool plan, rewrite/retry,
  abstention, HITL approval, and report-generation flows;
- typed state schema validation and bounded retry/reflection behavior.

Gate metrics:

| metric | target |
|---|---:|
| `planner_executor_or_supervisor_worker_pass` | `1.0` |
| `multi_tool_plan_pass` | `1.0` |
| `bounded_retry_reflection_pass` | `1.0` |
| `human_approval_node_pass` | `1.0` |
| `state_schema_validation_pass` | `1.0` |

Stop condition: do not add agent complexity unless the scenario needs planning,
tool sequencing, or approval semantics that the current graph cannot express.

## Phase 5: Security and reliability deepening

Goal: move from deterministic smoke checks to a reviewer-defensible
security/reliability report.

Required evidence:

- `artifacts/reliability_security/summary.json`;
- at least 20 red-team/security cases;
- deterministic replay or fallback reliability suite;
- PII/secrets leakage and prompt-injection results.

Gate metrics:

| metric | target |
|---|---:|
| `redteam_case_count` | `>= 20` |
| `prompt_injection_block_recall` | `1.0` |
| `secrets_pii_leak_count` | `0` |
| `fallback_recovery_pass` | `1.0` |
| `deterministic_replay_pass` | `1.0` |

Stop condition: do not persist raw prompts, raw RFP text, credentials, or
private provider payloads in public artifacts.

## Phase 6: Senior case study

Goal: package the technical judgment, not just the feature list.

Required evidence:

- `docs/portfolio/case-study.md`;
- architecture diagram or evidence map;
- explicit trade-off defense for parser lineage, vector retention, reranker
  deferral, Stage 2 vs Stage 3 claims, and production-adjacent wording;
- failure analysis and remaining risks.

Required sections:

- `Problem`;
- `Architecture decisions`;
- `Evaluation evidence`;
- `Failure analysis`;
- `Operational boundaries`;
- `Interview defense`.

## Failure conditions

The final top-tier claim is false if any of these are true:

- reviewer demo needs secrets, a long setup, or undocumented local state;
- Stage 3 eval reuses tuned examples or lacks split/hash/rubric evidence;
- observability shows only synthetic counters and no trace/failure evidence;
- agent upgrade is cosmetic and does not prove planning/tool sequencing;
- security evidence is limited to a few happy-path unit tests;
- case study cannot explain why the current limitations are honest boundaries.

## Readiness contract

`rfp_rag.portfolio_check` reports this under `top_tier_readiness`. It is
intentionally separate from the current `portfolio_readiness_check`: the current
repo can remain a completed production-adjacent evidence bundle while
`top_tier_readiness.complete=false` tracks the next level.

Completion requires:

- `portfolio_readiness_check=true`;
- `top_tier_readiness.complete=true`;
- local verification commands pass;
- GitHub CI passes after the final implementation PR.
