# Source-First RFP RAG Roadmap

## Current State

The project is a source-first RAG baseline.

- Primary text source: parsed HWP/PDF artifacts under `artifacts/parsed_docs`.
- `data/data_list.csv` is the metadata registry for project names, issuers, budgets, deadlines, and source filenames.
- Current retrieval, real/open/offline evaluation, agent lane, and hybrid retrieval experiments must be interpreted with their recorded source mode; new gate runs should not use CSV body text as an index source.

Observed source-file distribution on 2026-06-12:

| suffix | count |
|---|---:|
| `.hwp` | 96 |
| `.pdf` | 4 |

Local parser availability originally checked on 2026-06-12:

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

Goal:

- Parse original `data/files` HWP/PDF files into structured parse artifacts.
- Treat CSV as metadata only; never use CSV `텍스트` as a body-text fallback.
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

### 2. Source-First Indexing

Index construction must read text from the parse manifest:

- `--parse-manifest artifacts/parsed_docs/manifest.jsonl`
- fail closed when a document has no parsed source text
- do not provide a CSV text fallback mode

Index manifest should record:

- `text_source`
- `parse_manifest_path`
- `index_text_source_counts`
- parser lineage metadata copied onto chunks

### 3. Parsing EDA

Report:

- HWP/PDF ratio
- parse success rate
- empty parse count
- text length distribution
- parsed text length distribution
- top failure reasons
- sample parser warnings

### 4. Section-Aware Chunking

After source parsing works, add section metadata:

- `section_title`
- `section_type`
- `page_start`
- `page_end`
- `index_text_source`

Target section types:

- project overview
- requirements
- proposal submission
- eligibility
- evaluation criteria
- contract/deliverables

### 5. Retrieval Recalibration

Re-run vector, hybrid, and later reranker experiments against parsed source artifacts:

| text source | retrieval mode | purpose |
|---|---|---|
| parsed | vector | source-first gate baseline |
| parsed | hybrid | keyword recall experiment |

Hybrid retrieval must keep its current limitation explicit: it improved recall in the CSV baseline but reduced abstention accuracy at the vector-calibrated cutoff. Do not use hybrid as a gate until it has a source-specific no-answer strategy or calibrated cutoff.

## Portfolio Framing

The project should be described as:

> Public RFP source-document processing and source-first RAG evaluation over parsed HWP/PDF artifacts, with CSV limited to metadata, parser diagnostics, retrieval experiments, and grounded answer generation.

Avoid using CSV body text as a substitute for failed parsing. If source parsing fails, fix or diagnose the parser path before indexing.
