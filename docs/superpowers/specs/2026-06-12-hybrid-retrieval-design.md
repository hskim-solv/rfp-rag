# Hybrid Retrieval Design

## 1. Goal

Add a reproducible hybrid retrieval experiment lane that compares the current vector-only search against a BM25 + vector score fusion retriever.

This is not a final quality gate. It is an experiment surface for improving RFP retrieval recall, rank stability, and presentation-quality evidence in `REPORT.md`.

## 2. Scope

In scope:

- Keep the existing vector-only retrieval path as the default.
- Add an explicit retrieval mode: `vector` or `hybrid`.
- Build a lightweight BM25 index from the existing `chunks.jsonl`.
- Fuse vector and BM25 candidates into one ranked list.
- Record retrieval mode in evaluation outputs.
- Add tests for ranking behavior, invalid modes, and backward compatibility.
- Document the experiment command and interpretation.

Out of scope:

- Neural reranker integration.
- New embedding models.
- LangGraph agent behavior changes.
- UI work.
- Replacing `real_openai` gate semantics.

## 3. Architecture

The existing boundary is `rfp_rag.vector_index.search(store, query, top_k)`. It returns `SearchResult` objects used by `rag_chain`, `evaluate`, and agent nodes.

Hybrid retrieval should extend this boundary without breaking current callers:

- `search(...)` remains vector-only by default.
- A new `retrieval_mode` argument selects `vector` or `hybrid`.
- Hybrid mode receives an `index_dir` or chunk source so it can load `chunks.jsonl`.
- BM25 is implemented locally with a small deterministic tokenizer and no external service.
- Score fusion normalizes vector and BM25 ranks into a single score, preserving the existing `SearchResult.score` shape.

This keeps the change contained and lets evaluation compare:

```bash
python3 -m rfp_rag.evaluate ... --retrieval-mode vector
python3 -m rfp_rag.evaluate ... --retrieval-mode hybrid
```

## 4. Components

### BM25 Index

Create a focused retrieval helper, likely `rfp_rag/hybrid_retrieval.py`.

Responsibilities:

- Load chunks from `index_dir/chunks.jsonl`.
- Tokenize Korean/English/numeric text with deterministic regex tokenization.
- Build document frequencies and BM25 statistics.
- Score a query against all chunks.
- Return top BM25 candidates as `SearchResult`-compatible records.

The helper should avoid new runtime dependencies unless the standard implementation becomes too noisy. A compact in-repo BM25 is preferred for reproducibility.

### Fusion

Hybrid ranking combines vector and BM25 candidates:

- Retrieve more candidates than final `top_k` from both systems, e.g. `candidate_k = max(top_k * 4, 20)`.
- Normalize each candidate list by rank, using reciprocal rank fusion style scores:
  - vector contribution: `vector_weight / (rank_constant + rank)`
  - BM25 contribution: `bm25_weight / (rank_constant + rank)`
- Default weights:
  - vector: `0.7`
  - BM25: `0.3`
- Sort by fused score desc, then doc_id and chunk_id for deterministic ties.

This avoids comparing raw cosine and BM25 score scales directly.

### Evaluation Wiring

Add `retrieval_mode` through:

- `rag_chain.answer_with_store(...)`
- `rag_chain.answer_query(...)`
- `evaluate.evaluate_index(...)`
- `ask.py` CLI
- `evaluate.py` CLI

Metrics should include:

```json
{
  "retrieval_mode": "hybrid"
}
```

Predictions should continue to include `retrieved_doc_ids`, `retrieved_chunk_ids`, and `scores`.

## 5. Data Flow

Vector mode:

```text
query -> vector_index.search(store, query, top_k) -> SearchResult[]
```

Hybrid mode:

```text
query
  -> vector candidates from Qdrant
  -> BM25 candidates from chunks.jsonl
  -> reciprocal-rank fusion
  -> top_k SearchResult[]
```

The answer generation path is unchanged after retrieval.

## 6. Error Handling

- Unknown `retrieval_mode` raises `ValueError` before retrieval.
- Hybrid mode requires `index_dir/chunks.jsonl`; missing file raises `FileNotFoundError`.
- Empty BM25 tokens should return zero BM25 candidates and fall back to vector candidates.
- `top_k <= 0` still returns an empty result list.
- Evaluation should isolate per-question failures the same way it does today.

## 7. Testing

Add focused tests before implementation:

- Vector mode remains unchanged for existing tests.
- Hybrid mode can promote a keyword-exact chunk that vector-only ranks lower.
- Fusion is deterministic on ties.
- Invalid retrieval mode fails clearly.
- Evaluation writes `retrieval_mode` into `metrics.json`.
- CLI accepts `--retrieval-mode vector|hybrid`.

Run at completion:

```bash
uv run --group dev python -m pytest -m "not real" -q
```

For experiment evidence, run offline first:

```bash
uv run --group dev python -m rfp_rag.evaluate \
  --data data/data_list.csv --index artifacts/index \
  --out artifacts/eval_hybrid_offline \
  --provider offline --top-k 5 --min-score 0.15 --retrieval-mode hybrid
```

Open lane can be used after offline tests pass:

```bash
set -a; source .env; set +a
uv run --group dev python -m rfp_rag.evaluate \
  --data data/data_list.csv --index artifacts/index_open \
  --out artifacts/eval_open_hybrid \
  --provider open --top-k 5 --min-score 0.55 --retrieval-mode hybrid
```

## 8. Documentation

Update `README.md` and `REPORT.md` with:

- The new `--retrieval-mode` flag.
- A vector vs hybrid comparison table.
- A clear note that hybrid is an experiment lane, not a replacement for `real_openai` final gate.

## 9. Acceptance Criteria

- Existing vector mode tests pass unchanged.
- Hybrid mode has deterministic unit coverage.
- Evaluation artifacts record `retrieval_mode`.
- Offline hybrid evaluation runs successfully.
- `REPORT.md` contains a reproducible vector vs hybrid comparison section.
- No API keys are required for the base hybrid implementation and offline evaluation.

## 10. Self-Review

- No placeholder requirements remain.
- Scope is limited to BM25 + vector fusion; reranker/UI/agent changes are excluded.
- The design preserves existing default behavior by keeping vector mode as default.
- The scoring design avoids raw score-scale mixing by using rank-based fusion.
