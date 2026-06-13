# CSV-first RFP RAG Baseline

입찰 RFP 100건의 CSV `텍스트` 컬럼을 MVP source of truth로 사용하는 로컬 RAG 스캐폴드입니다. 원본 HWP 파싱은 별도 artifact lane에서 품질을 계측하며, 현재 RAG index 기본 입력은 CSV `텍스트`입니다. offline lane은 파일명 정규화, corpus/index 계약, cited QA schema, abstention, report artifacts를 검증합니다.

## Gate semantics

Contract: `rfp-rag-offline-v1`.

The offline lane (`--provider offline`) is an offline contract gate and does not claim semantic quality. It verifies deterministic corpus/index/retrieval plumbing, citation schema, and abstention behavior without credentials. The offline lane earns `offline_scaffold_complete` only (`thresholds_applied` stays false); `rag_quality_complete` is reserved for the real provider lane below. `--min-score 0.15` is the calibrated offline retrieval cutoff (rationale: `score_distribution` in `artifacts/eval/metrics.json`).

## Commands

```bash
python3 -m pytest
python3 -m rfp_rag.inspect_corpus --data data/data_list.csv --files data/files --out artifacts/corpus_manifest.json
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index --chunk-size 500 --chunk-overlap 80 --embedding-provider offline
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index --out artifacts/eval --provider offline --top-k 5 --min-score 0.15
python3 -m rfp_rag.report_check --eval artifacts/eval --readme README.md
```

## Source parsing lane

The current RAG path remains CSV-first. Source parsing is a separate artifact lane
that extracts original source text and records parser quality before parsed text
is used for indexing.

```bash
python3 -m rfp_rag.parse_sources --data data/data_list.csv --files data/files --out artifacts/parsed_docs
```

Outputs:

- `artifacts/parsed_docs/manifest.jsonl`
- `artifacts/parsed_docs/summary.json`
- `artifacts/parsed_docs/text/*.txt` for parsed documents
- `artifacts/parsed_docs/pdf/*.pdf` for page-citation evidence
- `artifacts/parsed_docs/page_text/*.jsonl` for extracted per-page text

The first implementation uses local `hwp5txt` for `.hwp` files and records
LibreOffice HWP-to-PDF conversion plus PyMuPDF page text when available. This
keeps searchable text extraction separate from page-level citation evidence. Use
`--no-page-citation` to skip this evidence pass in constrained local checks.

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

### Retrieval mode

`--retrieval-mode vector` is the default. `--retrieval-mode hybrid` fuses Qdrant
vector candidates with local BM25 candidates from `chunks.jsonl` using
reciprocal-rank fusion.

```bash
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index \
  --out artifacts/eval_hybrid_offline --provider offline --top-k 5 \
  --min-score 0.15 --retrieval-mode hybrid
```

Hybrid retrieval is an experiment lane. It improved offline retrieval metrics in
the current run, but reduced abstention accuracy at the vector-calibrated
`--min-score 0.15`; it does not replace the `real_openai` quality gate.

## Real provider quality lane (rfp-rag-real-v2)

Requires `OPENAI_API_KEY`. Models default to `text-embedding-3-small` /
`gpt-5.4-mini` (generation) / `gpt-5.4-mini` (judge — §10-11 A/B 검증, ADR-0005);
override via `RFP_EMBEDDING_MODEL`, `RFP_GENERATION_MODEL`, `RFP_JUDGE_MODEL`.

```bash
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files \
  --out artifacts/index_real --chunk-size 500 --chunk-overlap 80 --embedding-provider openai
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
  (offline lane: 0.15, real lane: 0.47). Record any recalibration rationale in the
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

## Open lane — 저비용 이터레이션 (rfp-rag-open-v1)

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
  --out artifacts/index_open --chunk-size 500 --chunk-overlap 80 --embedding-provider open
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
  --index artifacts/index --out artifacts/eval_agent --provider offline --top-k 5 --min-score 0.15

# 질문 1회 실행
python3 -m rfp_rag.agent.run_agent --index artifacts/index --data data/data_list.csv \
  --files data/files --question "사업 금액이 가장 큰 공고 3건은 뭐야?" --thread-id t1 --min-score 0.15

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
