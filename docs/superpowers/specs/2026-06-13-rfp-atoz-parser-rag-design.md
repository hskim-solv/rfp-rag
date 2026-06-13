# RFP A-to-Z Parser/RAG Direction Design

## 1. Goal

Record the project-level direction for turning the RFP prototype into an
employment-strong RAG engineering portfolio.

The product framing remains:

> A consultant-facing RFP intelligence copilot for Korean public-bid documents,
> focused on source-faithful search, summary, comparison, and recommendation.

The technical framing should not be "RFP chatbot". The stronger framing is:

> Source-preserving document ingestion -> section/table-aware indexing ->
> hybrid retrieval and reranking -> cited answer generation -> evaluation and
> trace gates -> MCP/agent service surface.

## 2. Current Local Baseline

Already present in the repository:

- CSV-first corpus and baseline RAG pipeline.
- Source parsing lane.
- Hybrid retrieval lane.
- Evaluation and judge contracts.
- Optional Langfuse tracing.
- LangGraph agent lane.
- Parser/render bakeoff harness and report path.

Already present or recently installed locally:

- `/Applications/LibreOffice.app`.
- `rhwp-python`.
- `unhwp` CLI under `~/.cargo/bin/unhwp`.

Known local gaps:

- `hwpxkit` is not installed.
- The bakeoff harness still needs real backend adapters for newly installed
  HWP/HWPX candidates.
- LibreOffice exists as an app bundle, but `soffice` is not necessarily on
  `PATH`; the harness should support explicit binary discovery.
- Current working tree has dependency-file changes from `rhwp-python`
  installation. Those changes are separate from this design record.

## 3. A-to-Z Candidate Axes

| Axis | Candidate set | Decision stance |
| --- | --- | --- |
| HWP/HWPX parsing | `rhwp-python`, `unhwp`, `hwpxkit`, `hwp-hwpx-parser`, `hwpkit`, `pyhwp`/`hwp5*` | Highest priority. Original source parsing quality is the current bottleneck. |
| HWP rendering/conversion | LibreOffice, H2Orestart extension, `rhwp` PDF/PNG/SVG rendering, `pyhwpxlib` preview/SVG | Needed for visual evidence review and table/chart preservation checks. |
| PDF parsing | PyMuPDF, PyMuPDF4LLM, pdfplumber, Docling, Unstructured, Marker, MarkItDown, MinerU, LlamaParse | Required for the PDF minority and for converted HWP evidence surfaces. |
| OCR and scanned documents | Tesseract, Mistral OCR, olmOCR, MinerU OCR/VLM pipeline, AWS Textract, Azure Document Intelligence | Defer until source parsing baseline is credible. Useful but higher scope/cost. |
| Table preservation | `rhwp` IR, `unhwp` Markdown/assets, Docling table model, pdfplumber tables | Critical because budgets, scoring criteria, schedules, and eligibility often live in tables. |
| Image/chart preservation | extracted assets, rendered page images, Docling chart understanding, MinerU chart/image parsing, visual document retrieval | Stretch differentiator. Do after text/table source quality is measured. |
| Chunking | section-aware, table-aware, parent-child, contextual chunks | Required to avoid a weak fixed-length-only RAG story. |
| Retrieval | BM25, dense vector, hybrid fusion, Reciprocal Rank Fusion | Hybrid is the required baseline for entity/date/budget-heavy RFPs. |
| Embeddings | OpenAI embeddings, BGE-M3, Voyage/Cohere embeddings | Compare Korean/entity recall and cost. BGE-M3 is attractive for multilingual sparse+dense experiments. |
| Reranking | bge-reranker, Cohere Rerank, cross-encoder, ColBERT-style methods | Use as a measured second-stage improvement, not an assumed win. |
| Evaluation | Recall@k, MRR, nDCG, faithfulness, citation accuracy, no-answer accuracy | Core portfolio proof. Changes should be accepted by metrics, not demos alone. |
| Observability | Langfuse, Phoenix, DeepEval/RAGAS, trace IDs | Turns failed retrieval/generation cases into inspectable engineering evidence. |
| Agent/MCP service surface | LangGraph workflow, FastMCP tools/resources/prompts | Add after ingestion/retrieval quality is credible. Strong serviceization signal. |

## 3.1 Latest Candidate Additions

After a fresh candidate check, add these newer or more currently relevant
options to the watchlist:

| Candidate | Category | Apply now? | Rationale |
| --- | --- | --- | --- |
| `rhwp-python` v0.7.0 | HWP/HWPX parser, renderer, HWPX writeback | Yes | Newer release adds HWPX writeback/HWP5-to-HWPX surface while preserving existing IR/render/MCP surfaces. Already installed locally, so it should be wired into the bakeoff first. |
| `hwpxkit` v0.2.1 | Rust-backed Python HWP/HWPX parser | Yes, if install remains light | Recent beta candidate with Python wheels and Markdown/HTML/JSON conversion. Good second HWP/HWPX parser comparison. |
| `hwpkit` | Pure-Python HWP/HWPX read/edit/extract | Candidate only | PyPI claims production/stable status and portable HWP/HWPX support. It needs local verification before trust because claims are broad. |
| Docling | Local PDF/document parser | Yes for PDF lane | Strong current candidate for structured PDF output, table structure, coordinates, JSON/Markdown, OCR, chart understanding, and MCP server support. |
| Marker + Surya | Local PDF/image to Markdown/JSON | Yes for PDF lane | Good speed-oriented local parser, especially useful as an alternative to Docling when throughput matters. License and model constraints must be checked before final adoption. |
| MinerU | Local document parser/OCR/VLM pipeline | Evaluate later | Strong-looking 2026 candidate for CJK, tables, formulas, images, charts, cross-page tables, and MCP integration. It is heavier and should not block the near-term HWP bakeoff. |
| LlamaParse v2 | Managed RAG parser API | Evaluate as quality ceiling | Useful if cloud upload is acceptable. Good benchmark ceiling for complex tables/charts, but not a default for private/local-first RFP ingestion. |
| Mistral OCR | Managed OCR/document AI API | Evaluate as OCR quality ceiling | Useful for scanned or visually complex PDFs. Defer until local parser baseline exists. |
| olmOCR | Open OCR/PDF linearization toolkit | Evaluate for scanned PDFs | Strong current OCR candidate for PDF linearization benchmarks. Defer until scanned documents are in scope. |
| PyMuPDF4LLM | Lightweight PDF to Markdown | Yes as cheap baseline | Fast, local, and simple for digital PDFs. Useful baseline even if not enough for complex layouts. |
| MarkItDown | Lightweight multi-format to Markdown | Candidate only | Useful for clean office/PDF files, but less structure-aware than Docling or Marker. Keep as a cheap fallback candidate. |
| ColQwen2.5 / Visual RAG Toolkit | Visual document retrieval | Stretch only | Stronger current visual retrieval direction than plain ColPali-only framing. Needs page rendering, GPU/MPS feasibility, and multi-vector index engineering. |

## 4. Recommended Build Order

### Phase 1: Parser/Renderer Bakeoff

Complete the parser/render bakeoff before wiring parsed source text into the
main index by default.

Primary candidates:

- `rhwp-python`: Python API, HWP/HWPX support, IR/JSON, rendering path.
- `unhwp`: Rust CLI/library candidate for Markdown/Text/JSON and assets.
- `hwpxkit`: Rust-backed Python parser/converter candidate.
- `hwpkit`: pure-Python parser/editor candidate to test as a portability
  fallback, not a trusted default.
- current `hwp5txt`, `hwp5html`, `hwp5odt`: baseline comparison.
- LibreOffice: visual/PDF conversion fallback if local binary invocation works.

Bakeoff outputs should compare:

- parse success rate
- extracted text length
- Markdown/HTML/JSON availability
- page count
- table count
- image/asset count
- render output availability
- elapsed time
- controlled failure reason

### Phase 2: Source-Aware Indexing

After the bakeoff picks a practical source strategy, extend chunks with source
metadata:

- document id
- project name
- agency
- source parser backend
- page/section if available
- section title
- table/image indicators
- source path and artifact path

This phase should make every answer traceable to a source chunk and, where
possible, a page/section/table artifact.

### Phase 3: Hybrid Retrieval and Reranking

Run retrieval ablations instead of presenting one pipeline as final.

Required comparisons:

1. vector-only baseline
2. metadata-filtered vector retrieval
3. BM25 + dense hybrid retrieval
4. hybrid retrieval + reranking

Primary metrics:

- Recall@5/10
- MRR@10
- nDCG@10
- metadata hit rate
- section hit rate
- citation support rate
- p50/p95 latency
- estimated cost/query

### Phase 4: Evaluation and Trace Gates

Build a frozen question set around consultant workflows:

- single-document fact extraction
- section-specific questions
- table/numeric questions
- multi-document comparison
- conditional RFP search
- follow-up questions
- unsupported/no-answer questions

Evaluation should combine deterministic retrieval metrics with human or
LLM-assisted answer review. Automatic faithfulness scores are useful, but they
must be spot-checked for Korean procurement/legal wording and numeric tables.

### Phase 5: Agent and FastMCP Service Surface

Do not lead with a broad autonomous agent. The agent layer should be a controlled
workflow and service surface around the proven RAG core.

Candidate FastMCP tools:

- `search_rfps`
- `compare_rfps`
- `extract_requirements`
- `summarize_rfp`
- `show_evidence`
- `run_parser_bakeoff`
- `read_eval_metrics`
- `report_gate_status`

Candidate MCP resources:

- parser bakeoff summaries
- evaluation metrics
- corpus manifest
- report artifacts
- source evidence snippets

This positions the project as a production-minded RAG/agent system rather than
another notebook-style chatbot.

## 5. Options Considered

### Option A: Retrieval-first, parser-faithful RAG copilot

This is the recommended path.

It focuses on original source fidelity, section/table-aware retrieval,
measured retrieval improvements, cited answers, and eval gates. It is the best
fit for a RAG/Retrieval Engineer portfolio because it creates defensible
evidence: parser quality, Recall@k, MRR, citation accuracy, latency, and failure
analysis.

### Option B: Agent-first workflow automation

This adds LangGraph/FastMCP early and frames the system as an agent platform.

This is useful later, but it is risky as the main path because an agent wrapped
around weak source parsing will still answer from weak evidence. Use this as the
serviceization layer after parser/retrieval quality improves.

### Option C: Multimodal/visual document intelligence

This explores page-image retrieval such as ColPali-style visual document
retrieval and multimodal answer generation.

This is a strong differentiator for tables, charts, and visually rich RFPs, but
it should be treated as a stretch lane after HWP-to-PDF/page rendering is stable.
It is higher scope and can distract from the core RAG engineering signal.

## 6. Recommended Decision

Choose Option A as the main line:

> Parser-faithful, source-aware, hybrid RAG for Korean public-bid RFPs.

Add Option B after the RAG core has measurable quality:

> FastMCP and LangGraph expose the system as typed tools/resources/workflows.

Keep Option C as a stretch differentiator:

> Visual document retrieval for layout-heavy pages, charts, and scanned/poorly
> parsed documents.

## 7. Near-Term Implementation Target

The next implementation plan should start with parser bakeoff expansion:

1. Detect local `soffice` from `/Applications/LibreOffice.app`.
2. Wire installed `rhwp-python` into the bakeoff as a real backend.
3. Wire installed `unhwp` CLI into the bakeoff with explicit path support.
4. Add optional dependency checks for `hwpxkit` and `hwp-hwpx-parser`.
5. Rerun the sample bakeoff and update `REPORT.md` with a recommendation.

No new UI or service layer should be added before the parser bakeoff produces a
credible source recommendation.

## 8. Source Notes

Research inputs used for this decision:

- Current HWP/HWPX candidates: `rhwp-python` v0.7.0, `hwpxkit` v0.2.1,
  `hwpkit`, `unhwp`, and related Hancom/HWPX tooling.
- Current PDF/document parsing candidates: Docling, Marker/Surya, MinerU,
  LlamaParse, Mistral OCR, olmOCR, PyMuPDF4LLM, and MarkItDown.
- Current visual retrieval candidates: ColPali, ColQwen2/2.5, ViDoRe V3,
  Qdrant/Weaviate multi-vector retrieval, and Visual RAG Toolkit.
- RAG evaluation survey: RAG systems need evaluation across retrieval and
  generation components, including relevance, accuracy, and faithfulness.
- Text-and-table retrieval benchmarks: hybrid retrieval plus neural reranking is
  a strong candidate for heterogeneous text/table documents; BM25 remains
  important for exact numeric and entity-heavy queries.
- Visual document retrieval work such as ColPali and M3DocRAG: page-image
  retrieval can recover evidence that text extraction misses, but it is a
  higher-scope stretch for this project.
- FastMCP documentation: MCP tools/resources/prompts provide a useful service
  boundary for exposing proven RAG workflows to agent clients.

## 9. Self-Review

- Scope is focused on project direction and near-term parser/RAG sequencing.
- No implementation is specified as complete.
- No candidate is assumed to work without local bakeoff evidence.
- Agent/MCP and visual retrieval are explicitly deferred until the data plane is
  credible.
- Current dependency-file changes are acknowledged as separate local state.
