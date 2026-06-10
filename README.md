# CSV-first RFP RAG Baseline

입찰 RFP 100건의 CSV `텍스트` 컬럼을 MVP source of truth로 사용하는 로컬 RAG 스캐폴드입니다. 원본 HWP/PDF 파싱은 stretch이며, 현재 offline lane은 파일명 정규화, corpus/index 계약, cited QA schema, abstention, report artifacts를 검증합니다.

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

## Real provider quality lane (rfp-rag-real-v1)

Requires `OPENAI_API_KEY`. Models default to `text-embedding-3-small` /
`gpt-5.4-mini` (generation) / `gpt-5.4` (judge); override via
`RFP_EMBEDDING_MODEL`, `RFP_GENERATION_MODEL`, `RFP_JUDGE_MODEL`.

```bash
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files \
  --out artifacts/index_real --chunk-size 500 --chunk-overlap 80 --embedding-provider openai
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_real \
  --out artifacts/eval_real --provider real_openai --top-k 5
```

- `rag_quality_complete` requires every threshold in `artifacts/eval_real/metrics.json`
  (`thresholds`) plus `evaluation_valid` (error rate <= 10%).
- Calibrate `--min-score` per lane from `score_distribution` in `metrics.json`
  (offline lane: 0.15). Record any recalibration rationale in the evaluation report.
- Citation metrics compare retrieved chunks against expected docs (comparable across
  lanes); the LLM's self-reported citations (`last_cited_chunk_ids`) are diagnostic only.
- Qdrant runs in embedded local mode: single-process only. Delete
  `artifacts/index_real/qdrant` and rebuild to re-index. Production migration path
  is a Docker Qdrant server with the same client API.
- Offline lane stays credential-free: `python3 -m pytest -m "not real"` must pass
  without `OPENAI_API_KEY`.
- Full real cycle cost estimate: under $5 with default models (judge dominates;
  set `RFP_JUDGE_MODEL=gpt-5.4-mini` to cut cost to roughly $1).
- Assumption: the corpus is trusted public RFP documents; prompt-injection
  robustness against adversarial corpus content is out of scope for this cycle.

## Generated artifacts

- `artifacts/corpus_manifest.json`: row/file normalization inventory.
- `artifacts/index/manifest.json`, `artifacts/index/chunks.jsonl`, `artifacts/index/qdrant/`: offline lexical-hash index (embedded Qdrant).
- `artifacts/demo_answer.json`, `artifacts/demo_abstention.json`: cited QA and abstention examples.
- `artifacts/eval/contract.json`: versioned offline report/evaluation contract.
- `artifacts/eval/metrics.json`, `artifacts/eval/predictions.jsonl`, `artifacts/eval/report.md`: offline evaluation outputs.
