# Source-Aware RFP RAG Roadmap

## Current State

The project is a CSV-first RAG baseline.

- Primary text source: `data/data_list.csv` column `텍스트`
- Source files are resolved and validated, but original HWP/PDF contents are not parsed into the corpus yet.
- Current retrieval, real/open/offline evaluation, agent lane, and hybrid retrieval experiments should be interpreted as CSV-baseline evidence.

Observed source-file distribution on 2026-06-12:

| suffix | count |
|---|---:|
| `.hwp` | 96 |
| `.pdf` | 4 |

Local parser availability on 2026-06-12:

| tool/library | status |
|---|---|
| `hwp5txt` | available |
| `hwp5html` | available |
| `hwp5odt` | available |
| `pdftotext` | unavailable |
| `fitz` / PyMuPDF | unavailable |
| `pdfplumber` | unavailable |
| `pypdf` | unavailable |

One sampled HWP file parsed with `hwp5txt` successfully:

- return code: `0`
- stdout chars: `25658`
- stdout non-empty: `true`
- stderr was non-empty, so parser diagnostics must be retained separately from success/failure.

## Roadmap

### 1. Source Parsing Lane

Create `feature/source-parsing-lane`.

Goal:

- Parse original `data/files` HWP/PDF files into structured parse artifacts.
- Keep CSV text as fallback, not as the only source.
- Produce parser EDA and failure diagnostics.

Primary output:

- `artifacts/parsed_docs/manifest.jsonl`
- `artifacts/parsed_docs/text/{doc_id}.txt`
- `artifacts/parsed_docs/summary.json`

Per-document manifest fields:

- `doc_id`
- `csv_row_id`
- `source_path`
- `source_suffix`
- `parser_backend`
- `parse_status`
- `text_path`
- `text_length`
- `stderr_length`
- `error_reason`
- `csv_text_length`
- `parsed_to_csv_length_ratio`

### 2. Source-Aware Indexing

Add source selection to index construction:

- `--source csv`
- `--source parsed`
- `--source parsed-with-csv-fallback`

Index manifest should record:

- `source_mode`
- `parsed_success_count`
- `csv_fallback_count`
- `empty_parse_count`
- `parser_manifest_path`

Default should remain `csv` until parsed artifacts are available and evaluated.

### 3. Parsing EDA

Report:

- HWP/PDF ratio
- parse success rate
- empty parse count
- text length distribution
- CSV-vs-parsed length ratio
- top failure reasons
- sample parser warnings

### 4. Section-Aware Chunking

After source parsing works, add section metadata:

- `section_title`
- `section_type`
- `page_start`
- `page_end`
- `source_mode`

Target section types:

- project overview
- requirements
- proposal submission
- eligibility
- evaluation criteria
- contract/deliverables

### 5. Retrieval Recalibration

Re-run vector, hybrid, and later reranker experiments by source mode:

| source mode | retrieval mode | purpose |
|---|---|---|
| csv | vector | baseline continuity |
| parsed-with-csv-fallback | vector | source parsing impact |
| parsed-with-csv-fallback | hybrid | keyword recall experiment |

Hybrid retrieval must keep its current limitation explicit: it improved recall in the CSV baseline but reduced abstention accuracy at the vector-calibrated cutoff. Do not use hybrid as a gate until it has a source-specific no-answer strategy or calibrated cutoff.

## Portfolio Framing

The project should be described as:

> Public RFP source-document processing and source-aware RAG evaluation, starting from a CSV baseline and progressing toward HWP/PDF parsing, parser diagnostics, fallback indexing, retrieval experiments, and grounded answer generation.

Avoid claiming original RFP source parsing is complete until the parser manifest and source-aware index/evaluation artifacts exist.
