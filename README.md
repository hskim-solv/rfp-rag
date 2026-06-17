# Source-first RFP RAG Baseline

입찰 RFP 100건의 원본 HWP/PDF를 파싱해 RAG 본문으로 사용하는 로컬 RAG 스캐폴드입니다. CSV는 사업명, 발주기관, 예산, 마감일, 파일명 같은 메타데이터 registry로만 사용하고, index 본문은 `parse_sources`가 만든 parsed source artifacts에서 읽습니다. offline lane은 파일명 정규화, corpus/index 계약, cited QA schema, abstention, report artifacts를 검증합니다.

## Gate semantics

Contract: `rfp-rag-offline-v2`.

The offline lane (`--provider offline`) is an offline contract gate and does not claim semantic quality. It verifies deterministic corpus/index/retrieval plumbing, citation schema, and abstention behavior without credentials. The offline lane earns `offline_scaffold_complete` only (`thresholds_applied` stays false); `rag_quality_complete` is reserved for the real provider lane below. `--min-score 0.34` is the calibrated section-aware source-first offline retrieval cutoff. The current score distribution includes synthetic exact-section candidate scores for section lookup queries, so use the abstention/in-domain gap in `artifacts/eval/metrics.json` as a lane-specific calibration signal, not as pure vector-similarity evidence.

## Final portfolio contract

The final portfolio target is recorded in
`docs/portfolio/2026-rfp-rag-final-goal.md`. The adversarial readiness review is
recorded in `docs/portfolio/2026-rfp-rag-adversarial-review.md`. The project
should be framed as an `LLM/RAG AI Engineer` portfolio for complex-document
parsing, retrieval quality evaluation, citation-grounded generation, and
evidence-inspectable RAG/Agent backends, not as a generic RFP chatbot.

The quality contract is source-first:

- 100 original Korean public RFP HWP/PDF documents are the RAG body source of
  truth.
- CSV is a metadata registry only.
- Offline artifacts prove deterministic plumbing and regression safety.
- Existing real-lane artifacts prove semantic RAG quality only for their
  recorded index and contract. The latest parsed-source pipeline needs an
  explicitly approved source-first real rerun before it can claim binding
  semantic quality.
- Agent artifacts prove workflow routing, verification, audit, checkpoint, and
  HITL behavior after retrieval quality is established.

Adversarial roadmap lock:

1. Harden `gate_status` so stale or lineage-mismatched artifacts do not look
   portfolio-ready.
2. Expand the benchmark with 100-document coverage, hard negatives,
   paraphrases, cross-document questions, and section/table/visual slices before
   claiming retrieval or reranker wins.
3. Rebuild the real gate on a parsed-source index only after explicit cost
   approval.
4. Add an evidence surface that shows answers, citations, chunks, source
   previews, gate freshness, failures, latency, and token/cost estimates.
5. Keep agent and visual claims subordinate to retrieval quality and evidence
   inspectability.

## Commands

```bash
python3 -m pytest
python3 -m rfp_rag.inspect_corpus --data data/data_list.csv --files data/files --out artifacts/corpus_manifest.json
python3 -m rfp_rag.parse_sources --data data/data_list.csv --files data/files --out artifacts/parsed_docs
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index --chunk-size 500 --chunk-overlap 80 --embedding-provider offline --parse-manifest artifacts/parsed_docs/manifest.jsonl
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index --out artifacts/eval --provider offline --top-k 5 --min-score 0.34
python3 -m rfp_rag.report_check --eval artifacts/eval --readme README.md
python3 -m rfp_rag.gate_status
```

## Source parsing lane

The RAG path is source-first. `data_list.csv` remains the metadata registry, and
source parsing extracts original HWP/PDF text before indexing.

```bash
python3 -m rfp_rag.parse_sources --data data/data_list.csv --files data/files --out artifacts/parsed_docs
```

Outputs:

- `artifacts/parsed_docs/manifest.jsonl`
- `artifacts/parsed_docs/summary.json`
- `artifacts/parsed_docs/text/*.txt` for parsed documents
- `artifacts/parsed_docs/pdf/*.pdf` for page-citation evidence
- `artifacts/parsed_docs/page_text/*.jsonl` for extracted per-page text

For `.hwp` files, the source parser uses a measured failover chain:
`unhwp -> hwp5txt -> converted_pdf_pymupdf`. The manifest records the selected
`parser_backend`, `content_source`, `source_quality`, and `text_backend_attempts`
for each document. There is no CSV text fallback: if source parsing cannot
produce text, indexing fails instead of silently using the metadata CSV text.
LibreOffice HWP-to-PDF conversion plus PyMuPDF page text remains the page-level
citation evidence path.
Native `.pdf` files are parsed directly with PyMuPDF for source text and copied
as source-PDF citation evidence. Use `--no-page-citation` to skip this evidence
pass in constrained local checks.

## Parser/render bakeoff

Before parsed HWP output becomes an index source, the project compares parser and
renderer backends on representative RFP samples.

```bash
python3 -m rfp_rag.run_parser_bakeoff \
  --data data/data_list.csv \
  --files data/files \
  --parse-manifest artifacts/parsed_docs/manifest.jsonl \
  --out artifacts/parser_bakeoff
```

Outputs:

- `artifacts/parser_bakeoff/samples.json`
- `artifacts/parser_bakeoff/results.jsonl`
- `artifacts/parser_bakeoff/summary.json`

Optional backends such as `rhwp`, `unhwp`, `hwpxkit`, and LibreOffice are recorded
as `missing_dependency` when unavailable, so the bakeoff remains reproducible on
a minimal local setup.

`summary.json` also records `ingestion_recommendation`. The current local rule
separates searchable text from visual evidence: prefer `unhwp` for text/JSON,
prefer `libreoffice_pdf` for rendered PDF evidence, and keep `rhwp` experimental
until its timeout/DocInfo failures are resolved.

## Parser quality evaluation

After source parsing creates text, PDF, and page-text artifacts, run deterministic
quality evaluation:

```bash
python3 -m rfp_rag.run_parser_quality_eval \
  --parsed-dir artifacts/parsed_docs \
  --out artifacts/parser_quality
```

Outputs:

- `artifacts/parser_quality/per_doc.jsonl`
- `artifacts/parser_quality/summary.json`
- `artifacts/parser_quality/risky_docs.jsonl`

The evaluator scores parsed text against PDF page text, tracks page-citation
coverage, estimates table-like line preservation, and records image/drawing
signals from PyMuPDF. Drawing-heavy pages are treated as chart candidates, not as
confirmed chart understanding; OCR/VLM judging is a later quality layer.

## Visual parsing audit

Before adding OCR/VLM parsing, select a bounded review set from parser-quality
signals:

```bash
python3 -m rfp_rag.run_visual_audit \
  --parsed-dir artifacts/parsed_docs \
  --quality-dir artifacts/parser_quality \
  --out artifacts/visual_audit \
  --max-docs 15 \
  --max-pages-per-doc 5
```

Outputs:

- `artifacts/visual_audit/summary.json`
- `artifacts/visual_audit/samples.jsonl`
- `artifacts/visual_audit/review.md`

This lane does not claim visual understanding. It ranks documents and pages with
chart/drawing/image/table-loss signals, then asks a human reviewer to label
whether the selected visual elements contain bid-review information that is not
already recoverable from extracted text.

Manual review on 2026-06-15 found repeated visual-only business information in
Gantt schedules, organization charts, system architecture diagrams, target
service models, and dashboard screenshots. The adopted next step is a targeted
page-level visual-structure extraction lane, not full OCR/VLM replacement of the
text pipeline. See
`docs/evidence/visual-audit-manual-review-2026-06-15.md` and
`docs/adr/0007-targeted-visual-structure-extraction.md`.

Create the first targeted visual-structure seed artifacts from the manual review
evidence:

```bash
python3 -m rfp_rag.run_visual_structure_extraction \
  --audit-dir artifacts/visual_audit \
  --review docs/evidence/visual-audit-manual-review-2026-06-15.md \
  --out artifacts/visual_structure
```

Outputs:

- `artifacts/visual_structure/records.jsonl`
- `artifacts/visual_structure/summary.json`
- `artifacts/visual_structure/review_queue.md`

The seed lane emits page/type records with `doc_id`, `page`, `visual_type`,
`business_fields`, `evidence_ref`, `extractor`, `confidence`, and
`review_status`. `structured_facts` intentionally starts empty until a targeted
extractor or reviewer fills facts for each queued visual record.

Reviewer facts are merged through a separate gold-set lane:

```bash
python3 -m rfp_rag.run_visual_fact_review \
  --records artifacts/visual_structure/records.jsonl \
  --facts docs/evidence/visual-structure-review-facts.seed.jsonl \
  --out artifacts/visual_structure_reviewed
```

This is the A-first path for visual facts. The reviewer fact JSONL is the gold
set for later OCR/VLM comparison: accepted facts are merged into
`structured_facts`, rejected facts become negative gold labels, and needs-review
facts remain unmerged. OCR/VLM extraction stays deferred until a candidate
extractor can be scored against this reviewer gold set.

Check whether the reviewed gold set is complete enough to trust as a comparison
baseline:

```bash
python3 -m rfp_rag.run_visual_gold_check \
  --summary artifacts/visual_structure_reviewed/summary.json
```

The default target is `resolved_record_ratio >= 0.80` with no unresolved
`needs_review` or unknown-record counts. Rejected facts count as resolved
negative labels, so a page-reviewed gold set can evaluate both recall and
precision for later OCR/VLM candidates.

Current expanded gold result: `fact_count=110`, `accepted_fact_count=25`,
`rejected_fact_count=85`, `resolved_record_ratio=1.0`,
`needs_review_fact_count=0`, and `unknown_record_count=0`. The gold set is now a
complete comparison set over the current 110 visual records, not only the
initial 60-record calibration subset.

Create the next reviewer batch for visual records that still require page review
or confirm that none remain:

```bash
python3 -m rfp_rag.run_visual_review_batch \
  --records artifacts/visual_structure/records.jsonl \
  --facts docs/evidence/visual-structure-review-facts.seed.jsonl \
  --out artifacts/visual_review_batch_next \
  --review-status needs_page_review
```

This writes `records.jsonl`, `facts_template.jsonl`, `summary.json`, and
`review_queue.md`. With the current expanded seed file, the command reports
`existing_fact_record_count=110` and `selected_record_count=0`, so there is no
remaining page-review batch for the current visual-structure records.

Evaluate a candidate extractor output against the reviewer gold set:

```bash
python3 -m rfp_rag.run_visual_gold_eval \
  --gold docs/evidence/visual-structure-review-facts.seed.jsonl \
  --candidate docs/evidence/visual-structure-candidate-facts.example.jsonl \
  --out artifacts/visual_gold_eval
```

The evaluator scores candidate facts by `(record_id, fact_type, field)` and
reports precision, recall, F1, negative-label violations, and unknown candidate
claims. The checked-in candidate file is only a smoke fixture, not an OCR/VLM
result.

Generate the deterministic no-model local baseline before adopting OCR/VLM:

```bash
python3 -m rfp_rag.run_visual_local_baseline \
  --records artifacts/visual_structure/records.jsonl \
  --out artifacts/visual_local_baseline_expanded \
  --review-status reviewed_needs_extraction \
  --review-status needs_page_review

python3 -m rfp_rag.run_visual_gold_eval \
  --gold docs/evidence/visual-structure-review-facts.seed.jsonl \
  --candidate artifacts/visual_local_baseline_expanded/candidate_facts.jsonl \
  --out artifacts/visual_local_baseline_expanded_eval
```

Current expanded local baseline result: `candidate_fact_count=110`,
`precision=0.19090909`, `recall=0.84`, `f1=0.31111111`,
`negative_violation_count=52`, and `unknown_candidate_count=37`. This is the
floor comparison group for later OCR/VLM or OCR+layout candidates, not a
production-quality visual extractor.

Generate the first local OCR candidate with Tesseract:

```bash
python3 -m rfp_rag.run_visual_tesseract_candidate \
  --records artifacts/visual_structure/records.jsonl \
  --out artifacts/visual_tesseract_candidate_expanded \
  --dpi 120 \
  --timeout-seconds 15 \
  --review-status reviewed_needs_extraction \
  --review-status needs_page_review

python3 -m rfp_rag.run_visual_gold_eval \
  --gold docs/evidence/visual-structure-review-facts.seed.jsonl \
  --candidate artifacts/visual_tesseract_candidate_expanded/candidate_facts.jsonl \
  --out artifacts/visual_tesseract_candidate_expanded_eval

python3 -m rfp_rag.run_visual_candidate_check \
  --summary artifacts/visual_tesseract_candidate_expanded_eval/summary.json \
  --out artifacts/visual_tesseract_candidate_expanded_gate
```

Current expanded precision-hardened Tesseract candidate result:
`candidate_fact_count=26`, `precision=0.76923077`, `recall=0.8`,
`f1=0.78431373`, `negative_violation_count=3`, and
`unknown_candidate_count=3`. This now clears the current visual-candidate target
on precision, recall, F1, and rejected-label violations. The gate artifact is
`artifacts/visual_tesseract_candidate_expanded_gate/summary.json`; this remains
a local OCR candidate rather than final visual understanding.

Attach gate-passing visual facts to an answer as sidecar context:

```bash
python3 -m rfp_rag.ask \
  --index artifacts/index \
  --query "제안요청서의 일정표나 요구사항표 근거를 함께 보여줘" \
  --visual-candidates artifacts/visual_tesseract_candidate_expanded/candidate_facts.jsonl \
  --visual-gate artifacts/visual_tesseract_candidate_expanded_gate/summary.json
```

The sidecar path keeps source-first boundaries intact. It checks the visual
candidate gate before loading facts, leaves retrieval ranking and indexed source
chunks unchanged, renders visual facts under `시각근거:` in the generator/judge
context, and exposes them as `sources[].visual_evidence`.

## Section-aware indexing

`build_index` detects coarse RFP sections before chunking. Each chunk carries
`section_title`, `section_type`, `section_path`, optional page fields, and
`requirement_ids`. Retrieval prepends section metadata to vector/BM25 text, and
answer sources expose section/page fields for citation review. When a query
contains the literal word `섹션` and an exact `section_title`, vector retrieval
also injects exact section-title candidates from `chunks.jsonl` before ranking,
so the offline section lookup eval is not limited by dense/lexical vector
collisions.

`evaluate` writes `section_lookup_questions.jsonl` and reports
`section_hit_rate`. Current offline calibration uses `--min-score 0.34`; the
section-aware score distribution is recorded in `artifacts/eval/metrics.json`
and includes injected section-candidate scores for the section lookup subset.

### Retrieval mode

`--retrieval-mode vector` is the default. `--retrieval-mode hybrid` fuses Qdrant
vector candidates with local BM25 candidates from `chunks.jsonl` using
reciprocal-rank fusion.

```bash
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index \
  --out artifacts/eval_hybrid_offline --provider offline --top-k 5 \
  --min-score 0.34 --retrieval-mode hybrid
```

Hybrid retrieval is an experiment lane. It must be calibrated separately before
being treated as an offline scaffold signal; it does not replace the
`real_openai` quality gate.

Current section-aware offline comparison at `--min-score 0.34`:

| mode | recall@5 | mrr | citation_validity | abstention_pass | section_hit_rate | offline_scaffold_complete |
|---|---:|---:|---:|---:|---:|---|
| vector | `1.0` | `1.0` | `1.0` | `1.0` | `1.0` | `true` |
| hybrid | `1.0` | `1.0` | `1.0` | `0.2` | `0.7` | `false` |

Interpretation: hybrid RRF expands candidates but is over-permissive for
abstention and loses the exact section-title candidate behavior that protects
section lookup. Keep `vector` as the offline gate mode until hybrid has its own
calibration/reranking strategy.

### Reranker

`--reranker none` is the default for both `ask` and `evaluate`. `--reranker llm`
adds a lane-compatible LLM reranker that reranks a larger candidate pool from
the existing retriever via `--rerank-candidate-k`, then returns the top-k chunks
to generation and evaluation. The implementation is intentionally limited to
`real_openai` and `open` lanes; offline evaluation rejects `--reranker llm` so
the credential-free contract remains intact.

The current decision is ADR-0008: keep `vector` and `hybrid` as controls, skip a
full deterministic reranker, and evaluate the B path through the existing
real/open provider surfaces first. Actual `--reranker llm` runs require explicit
cost/API approval.

Example shape, after approving the relevant provider cost:

```bash
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_open \
  --out artifacts/eval_open_rerank --provider open --top-k 5 --min-score 0.55 \
  --reranker llm --rerank-candidate-k 10
```

## Real provider quality lane (rfp-rag-real-v3)

The contract version is bumped for code/report semantics. Regenerate
`artifacts/eval_real` before using real-lane artifacts as current evidence.

Requires `OPENAI_API_KEY`. Models default to `text-embedding-3-small` /
`gpt-5.4-mini` (generation) / `gpt-5.4-mini` (judge — §10-11 A/B 검증, ADR-0005);
override via `RFP_EMBEDDING_MODEL`, `RFP_GENERATION_MODEL`, `RFP_JUDGE_MODEL`.

```bash
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files \
  --out artifacts/index_real --chunk-size 500 --chunk-overlap 80 \
  --embedding-provider openai --parse-manifest artifacts/parsed_docs/manifest.jsonl
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_real \
  --out artifacts/eval_real --provider real_openai --top-k 5 --min-score 0.47
```

- `rag_quality_complete` requires every threshold in `artifacts/eval_real/metrics.json`
  (`thresholds`) plus `evaluation_valid` (error rate <= 10%).
- After a gate-semantics (contract) change, regenerate evidence without API calls:
  `python3 -m rfp_rag.evaluate --reaggregate --out artifacts/eval_real --provider real_openai`
  recomputes metrics/contract/report from the preserved `predictions.jsonl` and marks
  the output with `reaggregated_from_predictions: true`.
- Calibrate `--min-score` per lane from `score_distribution` in `metrics.json`
  (offline lane: 0.34, real lane: 0.47). Record any recalibration rationale in the
  evaluation report.
- Citation metrics compare retrieved chunks against expected docs (comparable across
  lanes); the LLM's self-reported citations (`last_cited_chunk_ids`) are diagnostic only.
- Qdrant runs in embedded local mode: single-process only. Delete
  `artifacts/index_real/qdrant` and rebuild to re-index. Production migration path
  is a Docker Qdrant server with the same client API.
- Offline lane stays credential-free: `python3 -m pytest -m "not real"` must pass
  without `OPENAI_API_KEY`.
- Full real cycle cost estimate: roughly $1 with default models (judge `gpt-5.4-mini`;
  set `RFP_JUDGE_MODEL=gpt-5.4` for the pricier reference judge, ~$5).
- Judge model A/B: 저장된 predictions에 judge만 재실행해 모델 간 점수 합치도를 비교
  (generation 재실행 없음 — judge 비용만 발생). `RFP_JUDGE_BASE_URL`/`RFP_JUDGE_API_KEY`로
  OpenAI 호환 백엔드(DeepSeek 등) judge도 같은 스크립트로 검증:
  `RFP_JUDGE_MODEL=gpt-5.4-mini PYTHONPATH=. python3 scripts/judge_ab.py
  --predictions artifacts/eval_real/predictions.jsonl --out artifacts/judge_ab`
- Assumption: the corpus is trusted public RFP documents; prompt-injection
  robustness against adversarial corpus content is out of scope for this cycle.

## Open lane — 저비용 이터레이션 (rfp-rag-open-v2)

The contract version is bumped for code/report semantics. Regenerate
`artifacts/eval_open` before using open-lane artifacts as current evidence.

오픈소스/저가 모델로 같은 평가 파이프라인을 돌리는 이터레이션 레인입니다
(채택 근거·백엔드 비교는 `docs/adr/0005-open-lane-backend-and-judge-strategy.md`).
**게이트 증거가 아닙니다** — judge 점수를 이터레이션 신호로만 쓰고,
`rag_quality_complete`는 real lane에서만 판정합니다.

- 생성 기본: DeepSeek `deepseek-v4-flash` (`DEEPSEEK_API_KEY` 필요, 60건 ~$0.05).
  `RFP_OPEN_BASE_URL=http://localhost:11434/v1` + `RFP_OPEN_MODEL=qwen3:8b`로
  로컬 Ollama 백업 전환 — OpenAI 호환 base_url 하나로 백엔드를 교체합니다.
- 임베딩 기본: 로컬 Ollama `bge-m3` (키 불필요, `ollama pull bge-m3` 선행).

```bash
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files \
  --out artifacts/index_open --chunk-size 500 --chunk-overlap 80 \
  --embedding-provider open --parse-manifest artifacts/parsed_docs/manifest.jsonl
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_open \
  --out artifacts/eval_open --provider open --top-k 5 --min-score 0.55
```

`--min-score 0.55`는 첫 성공 런의 `score_distribution`에서 보정한 open lane 전용 cutoff입니다. abstention top score 최댓값은 `0.49755216`, in-domain top score 최솟값은 `0.60993228`이고, 두 분포 사이의 gap에 cutoff를 둡니다.
- open lane 평가도 judge를 실행합니다 — 기본 judge는 OpenAI `gpt-5.4-mini`이므로
  `OPENAI_API_KEY`가 필요하고, DeepSeek judge(A/B 검증 후)는 `RFP_JUDGE_BASE_URL`로
  전환합니다.

## LangGraph agent lane (rfp-agent-v1)

LangGraph `StateGraph` 기반 stateful multi-step agent: 질의 라우팅(rag/metadata) →
검색 → 충분성 판정 → 질의 재작성 루프(≤2회) → 생성 → 인용 검증 → (저장 요청 시)
human-in-the-loop 승인. 그래프 토폴로지는 레인 공통이며 Router/Rewriter 두뇌만
offline 규칙 기반 / real LLM(`gpt-5.4-mini` structured output)으로 주입됩니다.

```bash
# agent 게이트 평가 (offline 판정 — API 키 불필요)
python3 -m rfp_rag.agent.evaluate_agent --data data/data_list.csv --files data/files \
  --index artifacts/index --out artifacts/eval_agent --provider offline --top-k 5 --min-score 0.34

# 질문 1회 실행
python3 -m rfp_rag.agent.run_agent --index artifacts/index --data data/data_list.csv \
  --files data/files --question "사업 금액이 가장 큰 공고 3건은 뭐야?" --thread-id t1 --min-score 0.34

# HITL: "...보고서로 저장해줘" 질문은 interrupt로 멈춤 → 같은 thread-id로 재개
python3 -m rfp_rag.agent.run_agent --index artifacts/index --data data/data_list.csv \
  --files data/files --thread-id t1 --approve   # 또는 --reject
```

- `agent_lane_complete`는 offline 레인에서 판정합니다 (그래프/도구/HITL/루프 종료는
  결정론적). real 레인은 `pytest -m real` 스모크로 보강합니다.
- 도구: `search_rfp`(읽기), `aggregate_metadata`(읽기 — 금액/마감일/발주기관
  필터·정렬·건수·합계), `save_report`(쓰기 — 승인 필수, 경로 탈출 차단).
- 모든 도구 호출은 `<artifacts>/audit.jsonl`에 기록됩니다
  (`ts/thread_id/tool/args/outcome/approved`).
- 상태는 `<artifacts>/checkpoints.sqlite`에 영속 — 프로세스를 종료해도 같은
  `--thread-id`로 승인 대기를 재개할 수 있습니다.

## Observability (optional Langfuse tracing)

`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`가 환경에 있으면 LangGraph 실행, LLM 생성,
ragas judge 호출이 Langfuse로 트레이싱됩니다 (`rfp_rag/tracing.py`, 채택 근거는
`docs/adr/0001-llm-observability-tool.md`). **키가 없으면 완전한 no-op** — offline lane의
credential-free 불변식에 영향이 없습니다. 키 설정은 `.env.example` 참조.

- `LANGFUSE_BASE_URL`은 선택값 (기본 Langfuse Cloud; self-host나 리전 인스턴스만 지정).
- CLI(run_agent / evaluate / evaluate_agent)는 종료 전에 트레이스를 flush하므로
  실행 직후 대시보드에서 확인할 수 있습니다 (예외로 중단돼도 flush됨).
- real lane 평가를 트레이싱하면 judge 비용이 호출·토큰 단위로 분해되어 보입니다.

## Generated artifacts

- `artifacts/corpus_manifest.json`: row/file normalization inventory.
- `artifacts/index/manifest.json`, `artifacts/index/chunks.jsonl`, `artifacts/index/qdrant/`: offline lexical-hash index (embedded Qdrant).
- `artifacts/demo_answer.json`, `artifacts/demo_abstention.json`: cited QA and abstention examples.
- `artifacts/eval/contract.json`: versioned offline report/evaluation contract.
- `artifacts/eval/metrics.json`, `artifacts/eval/predictions.jsonl`, `artifacts/eval/report.md`: offline evaluation outputs.
