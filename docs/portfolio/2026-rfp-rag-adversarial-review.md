# 2026 RFP RAG Adversarial Portfolio Review

Date: 2026-06-17

## Method

An independent read-only adversarial reviewer was asked to judge this repository
as a senior `LLM/RAG AI Engineer` portfolio. The reviewer was constrained to
repository evidence only and was forbidden from editing files, running paid/API
commands, exposing raw RFP text, or dumping artifacts.

Reviewed surfaces:

- `README.md`
- `REPORT.md`
- `docs/portfolio/2026-rfp-rag-final-goal.md`
- `docs/portfolio/*.md`
- `docs/adr/*.md`
- local gate artifacts and manifests where needed for claim validation
- repo-local Codex/Claude agent definitions

## Verdict

Main-agent decision: **senior-promising-but-not-yet**.

The adversarial reviewer returned `overclaimed`. That verdict is accepted for
any public or resume claim that presents the project as already senior-ready.
It is narrowed here to mean:

- current source-first offline evidence is useful and should be preserved;
- existing real-lane semantic evidence is not sufficient for the latest
  parsed-source pipeline;
- final senior portfolio claims must be gated behind the roadmap changes below.

## Acceptance Matrix

| id | review verdict | main decision | evidence checked | roadmap action |
|---|---|---|---|---|
| F-01 | blocker: latest source-first real semantic gate is missing | accept | `artifacts/index_real/manifest.json` has `chunk_count=286` and no parsed lineage; `artifacts/index/manifest.json` has `text_source=parsed`, `parse_manifest_path`, and `chunk_count=16459`; `artifacts/eval_real/contract.json` is `rfp-rag-real-v2` and uses the old build command | Add source-first real gate as a blocker before final claim. `gate_status` must fail stale or lineage-mismatched real evidence. |
| F-02 | major: eval set is too small and easy | accept | `rfp_rag/evaluate.py` defaults to `max_docs=10`; current real metrics have `query_set_counts.total=60`; current source-first offline set has `70` queries including section lookup | Add a hardened benchmark milestone before retrieval/reranker claims: stratified 100-document coverage, hard negatives, paraphrases, cross-document questions, section/table/visual slices, and per-slice metrics. |
| F-03 | major: final resume claim overstates hybrid/reranking/latency/cost | accept | current final claim names hybrid/reranking and latency/cost gates; `REPORT.md` says LLM reranker quality has not been run; hybrid offline has `abstention_pass=0.2` and `offline_scaffold_complete=false` | Split current safe claim from target final claim. Keep reranker as interface evidence until an approved quality/latency/cost run exists. |
| F-04 | major: evidence UX/service surface is missing | accept | final goal requires a dashboard/service, but repo has no `app/`, `server/`, `dashboard/`, `Dockerfile`, FastAPI, or Streamlit dependency | Keep service/dashboard as a senior-ready milestone, not a completed claim. Require answer, citation, chunk, source preview, gate, failure, latency, and cost visibility. |
| F-05 | major: gate status is too shallow | accept, implemented follow-up | `rfp_rag/gate_status.py` previously read boolean gate keys and optional metadata only; focused tests now cover stale real artifacts and stale agent policy | `gate_status` now validates contract version, source lineage, parse manifest, query-set counts, retrieval mode, reranker, and reaggregation status before reporting `overall_ok=true`. |
| F-06 | major: agent lane is stale relative to current retrieval policy | partial | agent metrics pass, but local artifact records `min_score=0.15` while current contract command uses `--min-score 0.34`; REPORT says real agent smoke was blocked by quota | Keep agent workflow proof, but do not present it as latest retrieval-stack or real-LLM quality. Re-run current offline agent lane and add real smoke only with explicit cost approval. |
| F-07 | medium: visual lane is candidate-level, not visual understanding | partial | README and ADR already disclaim final visual understanding; visual candidate gate has `precision=0.76923077`, `recall=0.8`, `f1=0.78431373`, `negative_violation_count=3`; sidecar attaches by `doc_id` | Preserve visual-risk evidence, but require page-specific visual/table eval and sidecar on/off answer comparison before stronger claims. |
| F-08 | medium: parser bakeoff is narrow for backend selection | partial | parser bakeoff covers 6 backend/sample results; 100-doc parser quality is stronger, but REPORT still records `visual_content_unparsed=100` | Treat current parser as text/source lock, not full layout understanding. Expand semantic table/visual validation separately. |

No finding was rejected.

## Forced Roadmap Changes

1. **Gate freshness before more quality claims.**
   Implemented follow-up: `python3 -m rfp_rag.gate_status` now stops reporting
   stale artifacts as portfolio-ready. It validates contract versions, source
   lineage, parsed-manifest linkage, query-set counts, retrieval mode, reranker
   mode, and reaggregation provenance.

2. **Harden the benchmark before reranker adoption claims.**
   The next retrieval milestone must create a stronger labeled set before
   celebrating dense/BM25/hybrid/reranker deltas. Required slices are metadata,
   curated semantic questions, section lookup, hard abstention, paraphrase,
   cross-document comparison, and visual/table facts.

3. **Rebuild the real gate on the parsed-source index.**
   Existing real evidence remains useful historical semantic evidence, but the
   final portfolio needs an approved `real_openai` run whose index manifest
   proves `text_source=parsed` and `parse_manifest_path`.

4. **Make evidence inspectable.**
   A small service/dashboard must show answer, citations, retrieved chunks,
   source preview, failure reason, gate freshness, latency, token/cost estimate,
   and trace identifiers. This is a portfolio evidence surface, not a chatbot UI.

5. **Keep agent and visual claims subordinate to retrieval evidence.**
   Agent workflow, HITL, visual sidecar, and MCP/FastMCP work are valuable only
   after source/retrieval quality and failure visibility are credible.

## Claims To Avoid Until Evidence Exists

- "The latest source-first HWP/PDF real semantic quality gate passed."
- "Hybrid or reranking improved retrieval quality."
- "Artifact-backed latency and cost gates are complete."
- "Production visual understanding or multimodal RAG is solved."
- "The repository is senior-ready as a public service/dashboard portfolio."
