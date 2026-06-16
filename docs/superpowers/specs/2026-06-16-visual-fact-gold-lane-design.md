# Visual Fact Gold Lane Design

## Decision

Use an evidence-first reviewer fact lane before any OCR/VLM extractor. The lane
creates a page-level gold set for visual facts linked to existing
`artifacts/visual_structure/records.jsonl` records. OCR/VLM extraction remains a
later candidate lane and must be evaluated against this reviewer gold set before
it can be trusted.

## Goal

Turn selected visual-structure records into a reviewer-validated comparison set
without adding model/API cost or changing the source-first RAG body.

## Scope

In scope:

- Define a strict JSONL schema for reviewer facts.
- Validate that each fact points to an existing visual record.
- Validate that a fact's business field and fact type match the visual record.
- Merge only accepted facts into `structured_facts`.
- Count accepted, rejected, needs-review, unsupported, and coverage metrics.
- Write reviewed artifacts to a new output directory.

Out of scope:

- Running OCR/VLM.
- Selecting a provider/model.
- Persisting raw page images or raw model inputs.
- Treating visual facts as the primary RAG body source of truth.

## Data Model

Input fact JSONL record:

```json
{
  "record_id": "doc:034:p1:gantt_schedule",
  "fact_type": "visual_type_present",
  "field": "schedule",
  "value": "Gantt schedule is present on the selected page",
  "evidence_quote": "manual page review",
  "reviewer": "manual_review",
  "status": "accepted",
  "confidence": 0.9,
  "notes": "Optional reviewer note"
}
```

Accepted statuses:

- `accepted`: merged into `structured_facts`.
- `rejected`: counted as negative gold evidence, not merged.
- `needs_review`: counted, not merged.

Accepted fact types:

- `visual_type_present`
- `business_field_affected`
- `schedule_milestone`
- `schedule_duration`
- `schedule_dependency`
- `requirement_item`
- `architecture_component`
- `architecture_integration`
- `ui_requirement`

The first two fact types support a conservative reviewer gold set before deeper
business facts are filled. The later fact types support detailed page-level
facts when reviewers extract specific milestones, requirements, and architecture
components.

## Outputs

The merge CLI writes:

- `records.jsonl`: visual records with accepted facts merged into
  `structured_facts`.
- `summary.json`: coverage and quality counters.
- `review_report.md`: human-readable status and unresolved items.

Summary metrics:

- `record_count`
- `reviewed_needs_extraction_count`
- `accepted_record_count`
- `accepted_record_ratio`
- `rejected_record_count`
- `needs_review_record_count`
- `resolved_record_count`
- `resolved_record_ratio`
- `fact_count`
- `accepted_fact_count`
- `rejected_fact_count`
- `needs_review_fact_count`
- `unsupported_claim_count`
- `unknown_record_count`

## Failure Conditions

The lane fails fast when:

- a fact references an unknown `record_id`;
- status is not one of `accepted`, `rejected`, `needs_review`;
- accepted facts are missing `value`, `field`, `fact_type`, reviewer, or
  `evidence_quote`;
- fact field is not one of the visual record's `business_fields`;
- fact type is incompatible with the visual record's `visual_type`.

## Evaluation Use

This lane produces the comparison set for future OCR/VLM extraction:

- recall: candidate extractor facts matched against accepted reviewer facts;
- precision: candidate extractor facts not present in accepted reviewer facts;
- field accuracy: schedule / requirements / architecture classification;
- citation alignment: `record_id`, `doc_id`, and page match;
- unsupported visual claim rate: candidate facts rejected by reviewer gold.

## Implementation Units

- `rfp_rag/visual_facts.py`: schema validation, merge, summary, artifact writer.
- `rfp_rag/run_visual_fact_review.py`: CLI wrapper.
- `tests/test_visual_facts.py`: unit and CLI tests.
- `README.md` and `REPORT.md`: commands, policy, and interpretation.
