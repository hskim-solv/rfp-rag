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
| F-01 | blocker: latest source-first real semantic gate is missing | resolved | `artifacts/index_real/manifest.json` now has `text_source=parsed`, `parse_manifest_path=artifacts/parsed_docs/manifest.jsonl`, and `chunk_count=16459`; `artifacts/eval_real/contract.json` is `rfp-rag-real-v5`; `python3 -m rfp_rag.gate_status` reports `real_rag.ok=true` and `overall_ok=true`. | Keep gate freshness as a blocker for final claims; stale or lineage-mismatched real evidence must fail. |
| F-02 | major: eval set is too small and easy | partial, no-cost hardening in progress | Current source-first offline and real sets have `query_set_counts.total=545`: 100-document metadata coverage, 30 hard abstention, 30 section lookup, 20 cross-document, 25 reviewed visual/table, and 30 paraphrase questions. | Finish the 30-question visual/table target and same-dataset ablations before retrieval/reranker claims. Keep per-slice metrics in REPORT/README. |
| F-03 | major: final resume claim overstates hybrid/reranking/latency/cost | accept | current final claim names hybrid/reranking and latency/cost gates; `REPORT.md` says LLM reranker quality has not been run; hybrid offline has `abstention_pass=0.2` and `offline_scaffold_complete=false` | Split current safe claim from target final claim. Keep reranker as interface evidence until an approved quality/latency/cost run exists. |
| F-04 | major: evidence UX/service surface is missing | accept | final goal requires a dashboard/service, but repo has no `app/`, `server/`, `dashboard/`, `Dockerfile`, FastAPI, or Streamlit dependency | Keep service/dashboard as a senior-ready milestone, not a completed claim. Require answer, citation, chunk, source preview, gate, failure, latency, and cost visibility. |
| F-05 | major: gate status is too shallow | accept, implemented follow-up | `rfp_rag/gate_status.py` previously read boolean gate keys and optional metadata only; focused tests now cover stale real artifacts and stale agent policy | `gate_status` now validates contract version, source lineage, parse manifest, query-set counts, retrieval mode, reranker, and reaggregation status before reporting `overall_ok=true`. |
| F-06 | major: agent lane is stale relative to current retrieval policy | partial, no-cost refresh complete | agent metrics previously recorded `min_score=0.15`; the local agent lane has now been rerun with `--min-score 0.34` and `gate.failed=[]` | Keep agent workflow proof as offline evidence. Real LLM smoke remains optional and requires explicit cost approval. |
| F-07 | medium: visual lane is candidate-level, not visual understanding | partial, first eval slice implemented | README and ADR disclaim final visual understanding; visual candidate gate has `precision=0.76923077`, `recall=0.8`, `f1=0.78431373`, `negative_violation_count=3`; reviewed visual evidence now drives a 25-question `visual_table` slice with `visual_evidence_hit_rate=0.92` | Preserve visual-risk evidence, finish >=30 page-specific visual/table labels, and add sidecar on/off answer comparison before stronger claims. |
| F-08 | medium: parser bakeoff is narrow for backend selection | partial | parser bakeoff covers 6 backend/sample results; 100-doc parser quality is stronger, but REPORT still records `visual_content_unparsed=100` | Treat current parser as text/source lock, not full layout understanding. Expand semantic table/visual validation separately. |

No finding was rejected.

## Forced Roadmap Changes

1. **Gate freshness before more quality claims.**
   Implemented follow-up: `python3 -m rfp_rag.gate_status` now stops reporting
   stale artifacts as portfolio-ready. It validates contract versions, source
   lineage, parsed-manifest linkage, query-set counts, retrieval mode, reranker
   mode, and reaggregation provenance.

2. **Harden the benchmark before reranker adoption claims.**
   The no-cost benchmark now covers metadata, curated semantic questions,
   section lookup, hard abstention, cross-document comparison, paraphrase
   questions, and the first visual/table facts. The remaining benchmark
   hardening gap is the last 5 reviewed visual/table labels needed for the
   30-question visual/table target plus same-dataset ablations.

3. **Keep the real gate fresh on the parsed-source index.**
   Implemented follow-up: the approved `real_openai` run now uses
   `text_source=parsed`, `parse_manifest_path`, contract `rfp-rag-real-v5`, and
   the 545-query benchmark. Future contract or corpus changes must refresh it.

4. **Make evidence inspectable.**
   A small service/dashboard must show answer, citations, retrieved chunks,
   source preview, failure reason, gate freshness, latency, token/cost estimate,
   and trace identifiers. This is a portfolio evidence surface, not a chatbot UI.

5. **Keep agent and visual claims subordinate to retrieval evidence.**
   Agent workflow, HITL, visual sidecar, and MCP/FastMCP work are valuable only
   after source/retrieval quality and failure visibility are credible.

## Claims To Avoid Until Evidence Exists

- "Hybrid or reranking improved retrieval quality."
- "Artifact-backed latency and cost gates are complete."
- "Production visual understanding or multimodal RAG is solved."
- "The repository is senior-ready as a public service/dashboard portfolio."
