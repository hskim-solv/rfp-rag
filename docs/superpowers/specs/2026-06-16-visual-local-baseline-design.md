# Visual Local Baseline Candidate Design

## Decision

Before adopting OCR/VLM, add a deterministic no-model candidate lane. The lane
turns existing `artifacts/visual_structure/records.jsonl` records into candidate
visual facts and evaluates them against the reviewer gold set. This creates a
cheap lower-bound comparison group for later OCR/VLM candidates.

## Scope

In scope:

- Read visual-structure records.
- Emit candidate fact JSONL with `record_id`, `fact_type`, `field`, `value`,
  `extractor`, and `confidence`.
- Prefer field choices by visual type: schedule for Gantt, system architecture
  for architecture diagrams, requirements for organization charts, requirements
  tables, and dashboard screenshots.
- Write `candidate_facts.jsonl` and `summary.json`.
- Evaluate the generated candidate facts with the existing visual gold
  evaluator.

Out of scope:

- OCR.
- VLM/API calls.
- New dependencies.
- Treating this baseline as production visual extraction quality.

## Interpretation

The baseline is expected to have high recall on visually obvious records and low
precision because it trusts the existing visual-structure queue. That is useful:
it proves the evaluation harness can expose why a later OCR/VLM candidate is
better than a deterministic record-level baseline.
