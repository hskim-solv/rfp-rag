# Stage 3 Independent Holdout

This directory is reserved for the final top-tier independent holdout set.

Stage 3 is intentionally stricter than Stage 2:

- cases must come from a separate Stage 3 holdout split;
- each case must include `provenance.corpus_split =
  "stage3_independent_holdout"`;
- `provenance.stage2_overlap` must be `false`;
- `label_source` must be `manual_blind_label` or `dual_review_adjudicated`;
- cases must not be used for prompt, chunking, retrieval, reranker, or threshold
  tuning after freeze;
- paid real-provider evaluation requires explicit approval before execution.

The expected cases file is:

```text
eval_sets/stage3_holdout/cases.jsonl
```

Generate the frozen case file and local split metadata with:

```bash
uv run python -m rfp_rag.stage3_case_builder
```

Current limitation: this is a post-freeze query holdout on the fixed
100-document corpus. Stage 2 metadata evaluation already touched all 100
documents, so `contamination_notes.md` records that document-level overlap
explicitly. The builder still rejects exact Stage 2 query overlap and freezes
the generated queries before real-provider evaluation.

Schema:

```json
{
  "id": "stage3-000",
  "query": "reviewer-facing blind query",
  "query_type": "project_budget | project_deadline | issuer_lookup | project_summary | cross_document | abstention",
  "expected_doc_ids": ["stage3-doc-001"],
  "label_source": "manual_blind_label",
  "provenance": {
    "corpus_split": "stage3_independent_holdout",
    "stage2_overlap": false
  }
}
```

The contract finalizer is:

```bash
uv run python -m rfp_rag.stage3_holdout
```

After the cases are frozen and paid/API execution is approved, run the fixed-case
real evaluation:

```bash
uv run python -m rfp_rag.stage3_eval \
  --cases eval_sets/stage3_holdout/cases.jsonl \
  --index artifacts/index_real \
  --out artifacts/eval_stage3_raw \
  --provider real_openai \
  --top-k 5 \
  --min-score 0.47
```

Without `cases.jsonl` and a real metrics artifact, it writes a fail-closed
`artifacts/eval_stage3_holdout/metrics.json`. That is intentional: a missing or
unmeasured independent holdout must not look complete.
