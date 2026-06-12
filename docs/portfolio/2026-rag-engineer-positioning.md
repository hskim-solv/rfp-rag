# 2026 RAG Engineer Positioning

## Positioning

Target role:

- Retrieval & Evaluation Lead
- RAG / Retrieval Engineer
- LLM Application Engineer specializing in production RAG

Do not position this project as a generic RFP chatbot. The stronger framing is:

> Public-sector RFP document ingestion and source-aware RAG evaluation system for
> Korean HWP/PDF procurement documents.

The project should prove that the engineer can handle the hard parts of modern
RAG: parser fidelity, chunking, hybrid retrieval, reranking, citation grounding,
ablation, and evaluation.

## Market Signal

Current RAG hiring material consistently separates production RAG from tutorial
RAG. The repeated signals are:

- pure vector search is no longer enough
- chunking and parser quality are core retrieval work
- hybrid BM25 + dense retrieval is expected
- reranking is expected for serious systems
- context recall, faithfulness, citation quality, latency, and cost must be
  measured
- visually rich documents require page-level or multimodal retrieval paths

Useful source references:

- Recruo, "Hire RAG Engineers": production RAG candidates are screened for
  hybrid retrieval, rerankers, and eval harnesses, not notebook demos.
  https://recruo.com/hire-rag-engineers
- KORE1, "How to Hire RAG Engineers in 2026": retrieval-quality engineer lane
  owns chunking, embedding model evaluation, hybrid search, reranking, query
  rewriting, and eval pipelines.
  https://www.kore1.com/hire-rag-engineers-2026/
- AI Learning Guides, "RAG in Production 2026": production RAG is multi-stage
  retrieval with ingestion quality, hybrid indexes, reranking, evaluation, and
  observability.
  https://ailearningguides.com/rag-in-production-2026/
- ColPali paper: visually rich documents need retrieval that preserves layout,
  figures, and tables, not only extracted text.
  https://arxiv.org/html/2407.01449v4
- Microsoft ColPali reference: page-as-image retrieval preserves layout, charts,
  tables, and visual elements for multimodal RAG.
  https://github.com/microsoft/multi-modal-rag-with-colpali
- rhwp-python: candidate HWP/HWPX parser/renderer with text, IR/JSON,
  PDF/SVG/PNG rendering, and LangChain loader surfaces.
  https://github.com/DanMeon/rhwp-python
- unhwp: candidate HWP/HWPX Markdown/Text/JSON extractor with assets, tables,
  and images.
  https://github.com/iyulab/unhwp

## What To Build For Portfolio Value

### 1. Parser/Render Bakeoff

Why it matters:

RAG hiring now values ingestion quality. If a parser loses tables, charts, or
layout, retrieval cannot recover that information later.

Project evidence to produce:

- compare `hwp5txt`, `hwp5html`, `hwp5odt`, `rhwp-python`, `unhwp`, and optional
  `hwpxkit`
- record parse success rate, processing time, text length, table count, asset
  count, rendered page count, and error reasons
- manually score table/layout/image fidelity on representative RFPs
- recommend a default parser backend, visual evidence backend, and fallback path

Resume bullet:

> Designed a parser/render bakeoff for 100 Korean public RFP documents,
> comparing HWP text extraction, structured Markdown/JSON extraction, and
> PDF/SVG/PNG rendering to quantify table, image, and layout fidelity before
> source-aware indexing.

### 2. Source-Aware Indexing With Fallback

Why it matters:

Senior RAG candidates should show source selection and fallback discipline, not
silently swap corpus text.

Project evidence to produce:

- `--source csv`
- `--source parsed`
- `--source parsed-with-csv-fallback`
- index manifest records source mode, parser manifest, parsed count, fallback
  count, empty parse count, and unsupported count
- compare retrieval metrics by source mode

Resume bullet:

> Implemented source-aware indexing with CSV fallback, recording parser manifest
> lineage and measuring retrieval quality deltas between CSV text, parsed HWP
> text, and parsed-with-fallback modes.

### 3. Hybrid Retrieval And Reranking Ablation

Why it matters:

Production RAG signals are hybrid retrieval, reranking, and ablation. Dense-only
RAG reads as a 2023 demo.

Project evidence to produce:

- vector-only baseline
- BM25-only baseline
- hybrid dense + BM25 via RRF
- reranker on top-50 candidates
- query rewriting or metadata-aware query routing
- ablation table with Recall@5, MRR, citation validity, abstention accuracy,
  latency, and cost

Resume bullet:

> Built a retrieval ablation suite comparing dense, BM25, hybrid RRF, and
> reranked pipelines; reported Recall@5, MRR, citation validity, abstention
> accuracy, p95 latency, and per-query cost.

### 4. Eval Harness With Regression Gate

Why it matters:

The strongest hiring signal is not "I built RAG"; it is "I can prove retrieval
quality improved and prevent regressions."

Project evidence to produce:

- 50 to 100 labeled questions
- expected document and expected section/chunk labels
- query types: fact extraction, section lookup, comparison, condition search,
  unsupported/no-answer, follow-up
- metrics: Recall@k, MRR, section hit rate, context precision/recall,
  faithfulness, answer relevance, citation accuracy, no-answer accuracy
- regression gate that fails when metrics drop beyond threshold

Resume bullet:

> Created a labeled RFP retrieval evaluation set and regression gate tracking
> Recall@k, MRR, section hit rate, faithfulness, citation accuracy, and
> no-answer accuracy across parser, chunking, retrieval, and reranking changes.

### 5. Visual Evidence / Page-Level Retrieval

Why it matters:

RFPs often hide meaning in tables, figures, charts, and layout. A portfolio that
shows text RAG plus page/image evidence is more differentiated than another
chatbot.

Project evidence to produce:

- render relevant HWP/PDF pages to PNG/PDF/SVG
- attach source page preview to each cited answer
- optionally evaluate page-as-image retrieval with ColPali-style architecture
  after parser/render bakeoff
- build a visual-query eval subset for table/chart questions

Resume bullet:

> Added page-level visual evidence for cited RFP answers by rendering source
> documents and evaluating text retrieval against visually rich table/chart
> questions, preparing a path toward multimodal document RAG.

## Recommended Roadmap Order

1. Parser/render bakeoff
2. Source-aware indexing with CSV fallback
3. Section-aware chunking
4. Reranker and retrieval ablation
5. Evaluation set expansion and regression gate
6. Visual evidence UI
7. Optional page-as-image retrieval experiment

Do not lead with agents. Agentic workflow is useful after retrieval quality is
solid. For this portfolio, agent features should be framed as query routing,
retrieval strategy selection, answer verification, and HITL report approval.

## Final Portfolio Sentence

> Built a source-aware RAG system for Korean public RFP documents, including HWP
> parser/render bakeoff, CSV fallback indexing, section-aware chunking, hybrid
> retrieval, reranking, visual citation evidence, and a labeled evaluation gate
> for Recall@k, MRR, faithfulness, citation accuracy, latency, and cost.
