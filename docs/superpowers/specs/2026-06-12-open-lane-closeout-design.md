# Open Lane Closeout Design

## Context

The project already has three established lanes:

- `rfp-rag-offline-v1`: credential-free plumbing and contract gate.
- `rfp-rag-real-v2`: real provider quality gate; only this lane can claim `rag_quality_complete`.
- `rfp-agent-v1`: deterministic LangGraph workflow gate with optional real smoke tests.

The current branch, `feature/open-lane`, adds `rfp-rag-open-v1` as a low-cost iteration lane using open or cheaper OpenAI-compatible backends. The lane is intentionally not a quality gate. It should produce useful evidence for retrieval and generation iteration without weakening the real lane's quality contract.

## Goal

Close the open lane by producing reproducible local evidence, calibrating its retrieval cutoff from its own score distribution, and documenting how to interpret the results.

The result should answer:

- Can the open lane build an index and run evaluation with the configured backend?
- What `--min-score` is appropriate for the open lane's embedding score scale?
- What artifacts should future retrieval or model experiments compare against?
- Which claims are allowed for this lane, and which remain exclusive to the real lane?

## Non-Goals

- Do not make open lane output count as `rag_quality_complete`.
- Do not lower real lane thresholds or reuse open lane scores as real gate evidence.
- Do not start a broad model bakeoff in this closeout.
- Do not introduce a UI, FastMCP server, or new agent workflow in this closeout.
- Do not require paid provider calls for credential-free tests.

## Approach

Use an evidence-close lane.

1. Build `artifacts/index_open` with `--embedding-provider open`.
2. Run `rfp_rag.evaluate` with `--provider open` into `artifacts/eval_open`.
3. Inspect `artifacts/eval_open/metrics.json`, especially `score_distribution`.
4. Choose an open-lane-specific `--min-score` based on the first run.
5. Re-run or reaggregate if the code path supports it, so the final artifacts reflect the calibrated cutoff.
6. Update README and REPORT with the backend, model, judge, min-score, and interpretation.

If required services or credentials are unavailable, the implementation should fail fast with a clear note and preserve the offline gate invariant. Missing OpenAI, DeepSeek, or Ollama setup must not be treated as an offline regression.

## Data Flow

```text
data/data_list.csv
  -> rfp_rag.build_index --embedding-provider open
  -> artifacts/index_open
  -> rfp_rag.evaluate --provider open
  -> artifacts/eval_open/{metrics.json,predictions.jsonl,report.md,contract.json}
  -> README.md / REPORT.md closeout notes
```

The open lane should stay parallel to existing lanes. It may reuse shared corpus, chunking, provider, judge, and evaluation contracts, but its output directory and interpretation remain separate.

## Documentation Requirements

README should state:

- Open lane is an iteration signal, not gate evidence.
- The exact commands to build and evaluate the open lane.
- Required backend setup, including Ollama or OpenAI-compatible provider expectations.
- The calibrated `--min-score` and where the rationale lives.

REPORT should state:

- Backend/model/judge used for the closeout run.
- Final open-lane metrics.
- Min-score calibration rationale from `score_distribution`.
- Any limitations, skipped steps, or unavailable providers.
- How future hybrid retrieval, reranking, or model comparison work should use this baseline.

## Error Handling

- Missing `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, or Ollama should produce an actionable setup error, not a misleading quality failure.
- Open lane artifacts should not overwrite offline or real artifacts.
- If the first run produces no reliable in-domain/out-of-domain score separation, document that calibration is inconclusive instead of forcing a cutoff.
- If judge execution is unavailable, record that generation quality was not measured and only retrieval/index evidence was produced.

## Testing and Verification

Required verification:

- `python3 -m pytest -m "not real"` passes without provider credentials.
- `git status --short` is reviewed before commit so unrelated files, especially the existing untracked `uv.lock`, are not accidentally included.

Conditional verification:

- If open lane credentials/services are available, run the open index and evaluation commands and record the resulting metrics.
- If unavailable, document the exact missing prerequisite and leave implementation changes limited to clarity, guards, or docs.

## Future FastMCP Note

FastMCP is kept as a follow-up, not part of this closeout. The likely useful shape is an internal `RFP RAG Ops` MCP server that exposes safe operator tools such as `build_index_open`, `evaluate_open`, `read_lane_metrics`, `compare_lanes`, and `report_gate_status`.

## Acceptance Criteria

- `artifacts/eval_open` exists or the missing prerequisite is explicitly documented.
- Open lane `--min-score` is calibrated or marked inconclusive with evidence.
- README and REPORT clearly separate open iteration evidence from real quality gate evidence.
- Credential-free tests remain green.
- The closeout does not modify unrelated files or include `uv.lock` unless separately decided.
