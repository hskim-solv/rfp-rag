---
name: "eval-lane"
description: "Use when running RFP RAG/agent evaluation lanes, checking gate status, rebuilding indexes, comparing eval runs, or verifying gates before a PR."
---

# Eval Lane Runbook

## Trigger

Use this skill for `rfp-rag` evaluation work: offline RAG, real RAG, agent lane, gate status checks, run comparison, index rebuilds, and PR gate verification.

## Guardrails

- Offline lane must remain credential-free. `python3 -m pytest -m "not real"` must not require `OPENAI_API_KEY`.
- Real lane uses `OPENAI_API_KEY` and costs money. Do not run real RAG, real agent smoke, or `pytest -m real` unless the user explicitly asks for a real lane.
- `artifacts/` is gate evidence. Do not hand-edit metrics, predictions, reports, indexes, checkpoints, or audit logs.
- If a gate fails, hand off to `eval-gate-analyst` with a handoff_contract: destination, input payload, input filter, and return contract.

## Gate map

| Lane | Cost | Gate file | Gate key |
| --- | --- | --- | --- |
| offline RAG | free, no key | `artifacts/eval/metrics.json` | `offline_scaffold_complete` |
| real RAG | `OPENAI_API_KEY`, about $5 full run | `artifacts/eval_real/metrics.json` | `rag_quality_complete` |
| agent offline | free | `artifacts/eval_agent/metrics.json` | `agent_lane_complete`, plus `gate.failed[]` |
| visual candidate | free | `artifacts/visual_tesseract_candidate_expanded_gate/summary.json` | `ok` |
| real agent smoke | `OPENAI_API_KEY`, small cost | pytest result | `pytest -m real` passes |

## Gate status

Run from repo root:

```bash
python3 -m rfp_rag.gate_status
```

## Offline lane

Run when checking ordinary regressions. If `rfp_rag/agent/` changed, also run the agent lane.

```bash
python3 -m pytest -m "not real"
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index --chunk-size 500 --chunk-overlap 80 --embedding-provider offline --parse-manifest artifacts/parsed_docs/manifest.jsonl
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index --out artifacts/eval --provider offline --top-k 5 --min-score 0.34 --visual-records artifacts/visual_structure_reviewed/records.jsonl
python3 -m rfp_rag.report_check --eval artifacts/eval --readme README.md
```

## Agent lane

```bash
python3 -m rfp_rag.agent.evaluate_agent --data data/data_list.csv --files data/files \
  --index artifacts/index --out artifacts/eval_agent --provider offline --top-k 5 --min-score 0.34
```

If `metrics.json` has `gate.failed[]`, use `eval-gate-analyst`.

Handoff contract:
- destination: `eval-gate-analyst`
- input payload: failed metrics, relevant `metrics.json`, `predictions.jsonl`, `scenarios.jsonl`, and changed files
- input filter: do not include raw secrets, API keys, or full unrelated artifacts
- return contract: failed gate attribution, 2-3 evidence cases, and one smallest next experiment

## Real lane

Only after explicit user request:

```bash
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files \
  --out artifacts/index_real --chunk-size 500 --chunk-overlap 80 \
  --embedding-provider openai --parse-manifest artifacts/parsed_docs/manifest.jsonl
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_real \
  --out artifacts/eval_real --provider real_openai --top-k 5 --min-score 0.47 \
  --visual-records artifacts/visual_structure_reviewed/records.jsonl
python3 -m pytest -m real
```

If canonical `artifacts/index_real` evidence must be preserved, first run the
same build/eval with candidate output paths such as `artifacts/index_real_v5_candidate`
and `artifacts/eval_real_v5_candidate`. Building to an existing Qdrant path
recreates that local store.

Long-running evals write `eval_progress.jsonl`,
`predictions_unjudged_partial.jsonl`, `predictions_unjudged.jsonl`, and
`predictions_judged_partial.jsonl`. If real judge stalls or is interrupted,
inspect those files before rerunning; do not assume `metrics.json` exists until
the run completes.

Cost reduction option:

```bash
RFP_JUDGE_MODEL=gpt-5.4-mini
```

Rate-limit stabilization options for long real/open runs:

```bash
RFP_EVAL_ANSWER_DELAY_SECONDS=1
RFP_EVAL_ANSWER_RETRY_ATTEMPTS=5
RFP_EVAL_ANSWER_RETRY_DELAY_SECONDS=15
RFP_EVAL_JUDGE_START_DELAY_SECONDS=90
```

## Run comparison

```bash
python3 -c "
import json
a = json.load(open('artifacts/eval_real_run1/metrics.json'))['aggregate']
b = json.load(open('artifacts/eval_real/metrics.json'))['aggregate']
[print(f'{k}: {a.get(k)} -> {b.get(k)}') for k in sorted(set(a) | set(b))]
"
```

## Non-trigger

Do not use this skill for parser implementation, UI design, portfolio copy, or general refactoring unless the task also asks for gate execution or evaluation evidence.
