# Visual Tesseract Candidate Design

## Decision

Add a credential-free Tesseract OCR candidate lane for visual facts. The lane
renders reviewed visual-structure pages with `pdftoppm`, OCRs them with local
Tesseract Korean+English language data, converts visual-type keyword matches
into candidate facts, and evaluates those facts with the existing visual gold
evaluator.

## Scope

In scope:

- Read `artifacts/visual_structure/records.jsonl`.
- Process only `review_status == reviewed_needs_extraction`.
- Resolve each record's rendered PDF from `record.evidence_ref.pdf_path`.
- Render the target page to a temporary PPM image with `pdftoppm`.
- Run Tesseract through `stdin` using `-l kor+eng --psm 11`.
- Reuse OCR text by `(pdf_path, page)` because multiple visual records can point
  to the same rendered page.
- Emit candidate facts compatible with `run_visual_gold_eval`.
- Write `candidate_facts.jsonl`, `observations.jsonl`, and `summary.json`.

Out of scope:

- Hosted VLM/API calls.
- New Python OCR/ML dependencies.
- Persisting rendered page images.
- Treating OCR text as RAG source-of-truth.
- Claiming production-quality visual understanding.

## Candidate Policy

Candidate keys are intentionally aligned to the reviewer gold contract:

- `system_architecture_diagram` emits `(record_id, visual_type_present, system_architecture)`.
- `gantt_schedule` emits `(record_id, visual_type_present, schedule)`.
- `organization_chart` emits `(record_id, business_field_affected, requirements)`.
- `requirements_table` emits `(record_id, business_field_affected, requirements)`.

A candidate is emitted only when OCR text contains at least one visual-type
keyword. Empty OCR text and missing keyword evidence produce no candidate.

## Error Handling

Rendering/OCR errors are recorded in `observations.jsonl` and counted in
`summary.json`; they do not abort the whole lane. Missing `pdftoppm`, missing
Tesseract, missing PDF path, invalid page values, and per-page timeout all
produce per-record errors. This keeps the lane useful as a local capability
probe.

## Testing

Unit tests cover pure candidate building from supplied OCR text, JSONL artifact
writing, per-record error accounting, and CLI execution using an `--ocr-text`
fixture so tests do not require Tesseract or rendered PDFs. The real CLI path is
verified by running the lane on local visual artifacts after implementation.
