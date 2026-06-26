# Stage 2 RAG Quality Scorecard

Date: 2026-06-22

This document explains the deterministic Stage 2 quality scorecard used by the
senior portfolio roadmap. The machine-readable artifact is generated with:

```bash
uv run python -m rfp_rag.stage2_quality_scorecard
```

Output:

- `artifacts/stage2_quality_scorecard/summary.json`

## Purpose

The scorecard makes the RAG/parser quality claim reviewable in one place. It
aggregates existing evidence rather than running paid/API evaluation:

- parser quality: `artifacts/parser_quality/summary.json`
- retrieval bakeoff: `artifacts/retrieval_bakeoff/summary.json`
- visual/table quality: `artifacts/visual_quality/summary.json`
- Stage 2 frozen real evidence: `artifacts/eval_stage2_real/metrics.json`
- Stage 3 holdout quality: `artifacts/eval_stage3_holdout/metrics.json`
- Stage 3 raw predictions: `artifacts/eval_stage3_raw/predictions.jsonl`

## Acceptance Thresholds

| metric | threshold | reason |
| --- | ---: | --- |
| `parser_doc_count` | `>= 100` | all RFP corpus documents are covered |
| `parser_average_quality_score` | `>= 0.90` | parser quality is high enough for senior portfolio claim |
| `parser_page_citation_coverage` | `>= 1.0` | page-citation evidence exists for the corpus |
| `parser_low_quality_doc_count` | `<= 0` | no document is allowed below parser quality floor |
| `stage2_query_count` | `>= 150` | frozen Stage 2 evidence set is large enough |
| `stage3_query_count` | `>= 100` | Stage 3 holdout has the documented query count |
| `context_precision_at5` | `>= 0.70` | retrieved contexts should mostly point at expected documents |
| `context_recall_at5` | `>= 0.75` | expected evidence should be retrieved |
| `citation_precision_proxy` | `>= 0.90` | citation validity is used as the deterministic replacement for Ragas citation scoring |
| `unsupported_claim_rate` | `<= 0.03` | unsupported Stage 3 visual/table claims stay low |
| `stage3_faithfulness` | `>= 0.85` | real judged answers remain grounded |
| `stage3_answer_relevancy` | `>= 0.85` | answers are relevant enough for interview claim |
| `retrieval_no_regression` | `>= 1.0` | retrieval alternatives cannot regress recall/citation/abstention/visual/cost/latency |
| `visual_evidence_hit_rate` | `>= 0.90` | visual/table retrieval remains represented |

## Deterministic Context Metrics

Ragas is intentionally not reintroduced. The scorecard computes context metrics
from Stage 3 raw predictions:

- `context_precision_at5`: average fraction of retrieved document ids that are
  in `expected_doc_ids`, over answerable Stage 3 predictions.
- `context_recall_at5`: average fraction of expected document ids retrieved at
  least once, over answerable Stage 3 predictions.
- `citation_precision_proxy`: average `pass_fail.citation_validity` over
  answerable Stage 3 predictions.

This is not a public-traffic or unseen-document claim. It is a deterministic
portfolio quality gate over the fixed Stage 3 holdout.

## Reviewer Interpretation

If `stage2_quality_scorecard_complete=true`, the reviewer can treat the RAG
quality claim as backed by parser, retrieval, visual/table, frozen real, and
holdout evidence. If `failed` is non-empty, the senior portfolio claim should
pause until the underlying artifact is regenerated or the quality issue is
fixed.
