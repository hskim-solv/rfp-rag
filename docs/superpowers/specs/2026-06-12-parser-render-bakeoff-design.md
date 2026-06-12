# Parser/Render Bakeoff Lane Design

## 1. Goal

Select a practical backend strategy for Korean HWP/HWPX RFP ingestion before
parsed text is allowed to drive source-aware indexing.

The previous source parsing lane proved that `hwp5txt` can parse most local HWP
files:

- rows: 100
- suffixes: `.hwp` 96, `.pdf` 4
- statuses: `parsed` 94, `empty_text` 1, `parser_error` 1, `unsupported_suffix` 4
- parsed text files: 94

That is enough for a text baseline, but not enough for RFP fidelity. RFPs often
encode requirements, evaluation criteria, budgets, and submission rules inside
tables, figures, charts, headers, footers, and page layout. The next lane must
compare parser and renderer candidates before adding `--source parsed` indexing.

## 2. Design Decision

Run a small parser/render bakeoff first.

Do not immediately wire parsed output into `build_index`. The bakeoff should
answer two questions:

1. Which backend gives the best searchable text/Markdown/JSON for retrieval?
2. Which backend gives the best rendered evidence surface for tables, images,
   charts, and page-level citation review?

The target output is a documented recommendation, not a permanent parser
abstraction yet.

## 3. Candidate Backends

### Baseline Backends

- `hwp5txt`: current text baseline from pyhwp tooling.
- `hwp5html`: current local HTML converter candidate.
- `hwp5odt`: current local ODT converter candidate.

These are already available locally and should remain the baseline comparison.

### Primary New Candidates

- `rhwp-python`: HWP/HWPX parser/renderer candidate. It advertises text
  extraction, PDF/SVG/PNG rendering, IR/JSON, LangChain loader support, and
  table/image/formula/footnote-oriented document structures. It is promising
  but young, so local stability must be measured.
- `unhwp`: Rust HWP/HWPX to Markdown/Text/JSON with images/assets candidate.
  It is useful if Markdown plus extracted assets is enough for RAG and report
  review.
- `hwpxkit`: Rust-backed Python binding candidate with Markdown/HTML conversion
  and image output. Include only if install is straightforward in the local
  environment.

### Optional/Deferred Candidates

- `pyhwp2md` / `hwp2md`: lightweight Markdown candidates. Include as optional
  comparison if install friction is low, but do not make them the main path
  unless they handle the sample RFP tables better than expected.
- LibreOffice headless `HWP -> PDF`: use as a visual fidelity baseline if
  `soffice` can be installed/found locally. Its HWP filter is legacy, so it must
  be measured rather than trusted.
- Hancom SDK / Hancom COM: document as a production-quality commercial fallback,
  but do not require it for this local MVP. Windows/license constraints make it
  unsuitable for the default local lane.

## 4. Sample Set

Run the bakeoff on a representative subset first, not all 100 documents.

Selection rules:

- include the current `hwp5txt` `empty_text` document
- include the current `hwp5txt` `parser_error` document
- include several large parsed documents by text length
- include several high parsed-to-CSV ratio documents
- include several median-length documents
- include all 4 PDFs only for downstream PDF parser/render notes, not for HWP
  parser scoring

Default sample size:

- 12 HWP files
- 4 PDF files

The sample manifest should be deterministic and committed only as a lightweight
JSON/Markdown report if it contains no large extracted content. Heavy generated
outputs stay under ignored `artifacts/`.

## 5. Artifact Layout

Write bakeoff outputs under:

```text
artifacts/parser_bakeoff/
  samples.json
  results.jsonl
  summary.json
  backends/
    hwp5txt/
    hwp5html/
    hwp5odt/
    rhwp/
    unhwp/
    hwpxkit/
    libreoffice_pdf/
```

Per backend output may include:

- extracted text
- markdown
- html
- json/IR
- rendered pdf/svg/png files
- extracted images/assets
- stderr/stdout diagnostics

These artifacts are not committed because `artifacts/` is ignored.

## 6. Result Schema

Each backend/sample pair should produce one result record:

```json
{
  "doc_id": "doc:000",
  "source_path": "data/files/example.hwp",
  "backend": "rhwp",
  "status": "ok",
  "elapsed_ms": 1234,
  "text_length": 12000,
  "markdown_length": 15000,
  "html_length": 18000,
  "json_length": 25000,
  "page_count": 12,
  "table_count": 8,
  "image_count": 3,
  "rendered_pdf": true,
  "rendered_svg_count": 12,
  "rendered_png_count": 12,
  "asset_count": 3,
  "stderr_length": 0,
  "error_reason": null
}
```

Allowed statuses:

- `ok`
- `missing_dependency`
- `unsupported_format`
- `empty_output`
- `timeout`
- `backend_error`

## 7. Evaluation Metrics

Automated metrics:

- success rate by backend
- average and p95 elapsed time
- text length distribution
- CSV-to-output text length ratio
- table count
- image/asset count
- page/render output count
- backend warning/error counts

Manual review metrics for 5 to 8 representative documents:

- table fidelity score: 1 to 5
- chart/image evidence score: 1 to 5
- section/heading preservation score: 1 to 5
- human-readable output score: 1 to 5

Manual review should inspect generated HTML/PDF/SVG/PNG/Markdown rather than
only text length.

## 8. Acceptance Criteria

The lane is complete when:

- sample selection is deterministic
- each installed backend records a controlled result for every sample
- missing optional backends are recorded as `missing_dependency`, not failures
- `summary.json` ranks candidates by searchable output and rendered evidence
- `REPORT.md` records a recommendation:
  - default parser candidate
  - visual evidence/render candidate
  - fallback path
  - candidates deferred with reason

## 9. Recommended Outcome Shape

Expected decision categories:

- Retrieval text source: likely `rhwp-python` IR/text or `unhwp` Markdown if
  stable; otherwise keep `hwp5txt` with CSV fallback.
- Table-preserving source: likely `rhwp-python` IR/HTML or `unhwp` Markdown/HTML
  table fallback.
- Visual evidence source: likely `rhwp-python` PDF/SVG/PNG if it works locally;
  otherwise LibreOffice PDF as a fallback if available.
- PDF documents: evaluate with PyMuPDF/pdfplumber/Docling in a separate PDF lane
  unless the bakeoff reveals an easy dependency with strong results.

## 10. Out of Scope

- Replacing `build_index` input source.
- Adding a permanent parser plugin abstraction.
- Running real LLM/VLM evaluation on rendered pages.
- Installing commercial Hancom SDK or requiring Windows COM automation.
- Committing generated parse/render artifacts.

## 11. Self-Review

- The design does not assume `rhwp-python` works locally; it treats it as a
  candidate to measure.
- The design separates searchable output from rendered visual evidence.
- The design preserves the existing CSV-first RAG baseline until parser quality
  is documented.
- The design keeps generated artifacts ignored and records durable conclusions
  in docs.
