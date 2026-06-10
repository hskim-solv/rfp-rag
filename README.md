# CSV-first RFP RAG Baseline

입찰 RFP 100건의 CSV `텍스트` 컬럼을 MVP source of truth로 사용하는 로컬 RAG 스캐폴드입니다. 원본 HWP/PDF 파싱은 stretch이며, 현재 offline lane은 파일명 정규화, corpus/index 계약, cited QA schema, abstention, report artifacts를 검증합니다.

## Gate semantics

Contract: `rfp-rag-offline-v1`.

`fake_offline` is an offline contract gate and does not claim semantic quality. It verifies deterministic corpus/index/retrieval plumbing, citation schema, and abstention behavior. Real RAG quality requires a real provider/API key lane.

## Commands

```bash
python3 -m pytest
python3 -m rfp_rag.inspect_corpus --data data/data_list.csv --files data/files --out artifacts/corpus_manifest.json
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index --chunk-size 500 --chunk-overlap 80 --embedding-provider fake
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index --out artifacts/eval --provider fake_offline --top-k 5
python3 -m rfp_rag.report_check --eval artifacts/eval --readme README.md
```

If `OPENAI_API_KEY` is available, rebuild/evaluate with real providers in a separate quality lane and apply the thresholds from `artifacts/eval/metrics.json`. Without credentials, only `offline_scaffold_complete` may be claimed; `rag_quality_complete` must stay false.

## Generated artifacts

- `artifacts/corpus_manifest.json`: row/file normalization inventory.
- `artifacts/index/manifest.json`, `artifacts/index/chunks.jsonl`: local fake lexical index.
- `artifacts/demo_answer.json`, `artifacts/demo_abstention.json`: cited QA and abstention examples.
- `artifacts/eval/contract.json`: versioned offline report/evaluation contract.
- `artifacts/eval/metrics.json`, `artifacts/eval/predictions.jsonl`, `artifacts/eval/report.md`: offline evaluation outputs.
