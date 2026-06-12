# Hybrid Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible `--retrieval-mode hybrid` experiment that fuses Qdrant vector retrieval with local BM25 keyword retrieval while keeping vector retrieval as the default.

**Architecture:** Keep the existing `rfp_rag.vector_index.search()` vector path intact and add a focused `rfp_rag.hybrid_retrieval` helper for BM25 indexing and reciprocal-rank fusion. Thread `retrieval_mode` from CLI/evaluation/RAG entrypoints into retrieval and record it in metrics so vector and hybrid runs are comparable.

**Tech Stack:** Python 3.11, Qdrant local vector store, LangChain documents/embeddings, in-repo BM25 implementation, pytest.

---

## File Structure

- Create `rfp_rag/hybrid_retrieval.py`: deterministic tokenization, chunk loading, BM25 scoring, and rank-fusion helpers.
- Modify `rfp_rag/vector_index.py`: add retrieval mode constants and route `search(..., retrieval_mode="vector"|"hybrid", index_dir=None)` to vector-only or hybrid fusion.
- Modify `rfp_rag/rag_chain.py`: accept and pass `retrieval_mode`, and pass `index_dir` to retrieval for hybrid mode.
- Modify `rfp_rag/evaluate.py`: add `retrieval_mode` argument/CLI flag, pass it into `answer_query`, and write it into `metrics.json`.
- Modify `rfp_rag/ask.py`: add `--retrieval-mode` CLI flag.
- Modify tests: `tests/test_hybrid_retrieval.py`, `tests/test_vector_index.py`, `tests/test_rag_chain.py`, `tests/test_evaluate_report.py`.
- Modify docs: `README.md`, `REPORT.md`.

---

### Task 1: BM25 Helper

**Files:**
- Create: `rfp_rag/hybrid_retrieval.py`
- Test: `tests/test_hybrid_retrieval.py`

- [ ] **Step 1: Write failing BM25 helper tests**

Create `tests/test_hybrid_retrieval.py`:

```python
from __future__ import annotations

from pathlib import Path

from rfp_rag.chunking import Chunk
from rfp_rag.hybrid_retrieval import (
    BM25Index,
    fuse_ranked_results,
    load_chunk_results,
    tokenize,
)
from rfp_rag.index_store import save_index, SearchResult


def _chunk(chunk_id: str, text: str, project_name: str = "") -> Chunk:
    doc_num = chunk_id.split(":")[1]
    return Chunk(
        chunk_id=chunk_id,
        doc_id=f"doc:{doc_num}",
        csv_row_id=doc_num,
        text=text,
        metadata={
            "project_name": project_name,
            "issuer": "테스트기관",
            "csv_filename_raw": f"{doc_num}.pdf",
        },
    )


def _search_result(chunk_id: str, score: float) -> SearchResult:
    doc_num = chunk_id.split(":")[1]
    return SearchResult(
        chunk_id=chunk_id,
        doc_id=f"doc:{doc_num}",
        csv_row_id=doc_num,
        score=score,
        text=f"text {chunk_id}",
        metadata={"project_name": f"사업 {doc_num}", "issuer": "테스트기관"},
    )


def test_tokenize_keeps_korean_english_and_numbers() -> None:
    assert tokenize("AI 기반 LMS 2차 고도화, RFP-2026!") == [
        "ai",
        "기반",
        "lms",
        "2차",
        "고도화",
        "rfp",
        "2026",
    ]


def test_load_chunk_results_reads_chunks_jsonl(tmp_path: Path) -> None:
    out = tmp_path / "index"
    chunks = [_chunk("doc:000:chunk:0", "AI LMS 본문", "AI LMS 사업")]
    save_index(out, {"embedding_provider": "offline"}, chunks)

    loaded = load_chunk_results(out)

    assert loaded[0].chunk_id == "doc:000:chunk:0"
    assert loaded[0].doc_id == "doc:000"
    assert "사업명: AI LMS 사업" in loaded[0].text
    assert "발주기관: 테스트기관" in loaded[0].text
    assert loaded[0].metadata["csv_filename_raw"] == "000.pdf"


def test_bm25_scores_keyword_exact_chunk_first(tmp_path: Path) -> None:
    out = tmp_path / "index"
    chunks = [
        _chunk("doc:000:chunk:0", "범용 시스템 유지보수", "일반 유지보수"),
        _chunk("doc:001:chunk:0", "AI LMS 학습 분석 추천 엔진 구축", "AI LMS 고도화"),
    ]
    save_index(out, {"embedding_provider": "offline"}, chunks)
    index = BM25Index.from_index_dir(out)

    results = index.search("AI LMS 추천 엔진", top_k=2)

    assert results[0].chunk_id == "doc:001:chunk:0"
    assert results[0].score > results[1].score


def test_bm25_empty_query_returns_no_results(tmp_path: Path) -> None:
    out = tmp_path / "index"
    save_index(out, {"embedding_provider": "offline"}, [_chunk("doc:000:chunk:0", "AI LMS 본문")])
    index = BM25Index.from_index_dir(out)

    assert index.search("!!!", top_k=5) == []


def test_fuse_ranked_results_promotes_keyword_candidate() -> None:
    vector = [
        _search_result("doc:000:chunk:0", 0.90),
        _search_result("doc:001:chunk:0", 0.80),
    ]
    bm25 = [
        _search_result("doc:001:chunk:0", 12.0),
        _search_result("doc:002:chunk:0", 8.0),
    ]

    fused = fuse_ranked_results(vector, bm25, top_k=3, vector_weight=0.7, bm25_weight=0.3, rank_constant=1)

    assert [r.chunk_id for r in fused] == [
        "doc:001:chunk:0",
        "doc:000:chunk:0",
        "doc:002:chunk:0",
    ]
    assert fused[0].score > fused[1].score


def test_fusion_tie_breaks_deterministically() -> None:
    vector = [_search_result("doc:002:chunk:0", 0.9), _search_result("doc:001:chunk:0", 0.8)]
    bm25: list[SearchResult] = []

    fused = fuse_ranked_results(vector, bm25, top_k=2, vector_weight=1.0, bm25_weight=0.0, rank_constant=60)

    assert [r.chunk_id for r in fused] == ["doc:002:chunk:0", "doc:001:chunk:0"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --group dev python -m pytest tests/test_hybrid_retrieval.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'rfp_rag.hybrid_retrieval'`.

- [ ] **Step 3: Implement BM25 helper**

Create `rfp_rag/hybrid_retrieval.py`:

```python
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .index_store import SearchResult
from .vector_index import embedding_text

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in _TOKEN_RE.finditer(text)]


def load_chunk_results(index_dir: Path | str) -> list[SearchResult]:
    index_dir = Path(index_dir)
    chunks_path = index_dir / "chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"chunks file not found: {chunks_path}")
    results: list[SearchResult] = []
    with chunks_path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            metadata = dict(record.get("metadata") or {})
            text = embedding_text(
                type(
                    "_ChunkLike",
                    (),
                    {
                        "metadata": metadata,
                        "text": record.get("text", ""),
                    },
                )()
            )
            results.append(
                SearchResult(
                    chunk_id=record["chunk_id"],
                    doc_id=record["doc_id"],
                    csv_row_id=record["csv_row_id"],
                    score=0.0,
                    text=text,
                    metadata=metadata,
                )
            )
    return results


@dataclass(frozen=True)
class _DocStats:
    result: SearchResult
    term_counts: Counter[str]
    length: int


class BM25Index:
    def __init__(self, documents: list[SearchResult], *, k1: float = 1.5, b: float = 0.75) -> None:
        self._documents = documents
        self._k1 = k1
        self._b = b
        self._stats: list[_DocStats] = []
        document_frequency: Counter[str] = Counter()
        total_length = 0
        for document in documents:
            terms = tokenize(document.text)
            counts = Counter(terms)
            self._stats.append(_DocStats(document, counts, len(terms)))
            total_length += len(terms)
            document_frequency.update(counts.keys())
        self._document_frequency = document_frequency
        self._avgdl = total_length / len(documents) if documents else 0.0

    @classmethod
    def from_index_dir(cls, index_dir: Path | str) -> "BM25Index":
        return cls(load_chunk_results(index_dir))

    def _idf(self, term: str) -> float:
        n_docs = len(self._stats)
        if n_docs == 0:
            return 0.0
        df = self._document_frequency.get(term, 0)
        return math.log(1 + (n_docs - df + 0.5) / (df + 0.5))

    def _score(self, query_terms: list[str], stats: _DocStats) -> float:
        if not query_terms or stats.length == 0 or self._avgdl == 0:
            return 0.0
        score = 0.0
        for term in query_terms:
            tf = stats.term_counts.get(term, 0)
            if tf == 0:
                continue
            denominator = tf + self._k1 * (1 - self._b + self._b * stats.length / self._avgdl)
            score += self._idf(term) * ((tf * (self._k1 + 1)) / denominator)
        return score

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        if top_k <= 0:
            return []
        query_terms = tokenize(query)
        if not query_terms:
            return []
        scored: list[SearchResult] = []
        for stats in self._stats:
            score = self._score(query_terms, stats)
            if score <= 0:
                continue
            scored.append(
                SearchResult(
                    chunk_id=stats.result.chunk_id,
                    doc_id=stats.result.doc_id,
                    csv_row_id=stats.result.csv_row_id,
                    score=round(score, 8),
                    text=stats.result.text,
                    metadata=stats.result.metadata,
                )
            )
        scored.sort(key=lambda item: (-item.score, item.doc_id, item.chunk_id))
        return scored[:top_k]


def fuse_ranked_results(
    vector_results: list[SearchResult],
    bm25_results: list[SearchResult],
    *,
    top_k: int,
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3,
    rank_constant: int = 60,
) -> list[SearchResult]:
    if top_k <= 0:
        return []
    by_chunk: dict[str, SearchResult] = {}
    scores: dict[str, float] = {}

    def add(results: list[SearchResult], weight: float) -> None:
        for rank, result in enumerate(results, start=1):
            by_chunk.setdefault(result.chunk_id, result)
            scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + weight / (rank_constant + rank)

    add(vector_results, vector_weight)
    add(bm25_results, bm25_weight)

    fused: list[SearchResult] = []
    for chunk_id, score in scores.items():
        base = by_chunk[chunk_id]
        fused.append(
            SearchResult(
                chunk_id=base.chunk_id,
                doc_id=base.doc_id,
                csv_row_id=base.csv_row_id,
                score=round(score, 8),
                text=base.text,
                metadata=base.metadata,
            )
        )
    fused.sort(key=lambda item: (-item.score, item.doc_id, item.chunk_id))
    return fused[:top_k]
```

- [ ] **Step 4: Run BM25 helper tests**

Run:

```bash
uv run --group dev python -m pytest tests/test_hybrid_retrieval.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/hybrid_retrieval.py tests/test_hybrid_retrieval.py
git commit -m "feat: add local BM25 hybrid helpers"
```

---

### Task 2: Retrieval Mode Routing

**Files:**
- Modify: `rfp_rag/vector_index.py`
- Modify: `rfp_rag/rag_chain.py`
- Test: `tests/test_vector_index.py`
- Test: `tests/test_rag_chain.py`

- [ ] **Step 1: Add failing retrieval mode tests**

Append to `tests/test_vector_index.py`:

```python
import pytest

from rfp_rag.index_store import save_index
from rfp_rag.vector_index import RETRIEVAL_HYBRID, RETRIEVAL_VECTOR


def test_search_rejects_unknown_retrieval_mode() -> None:
    emb = LexicalHashEmbeddings(dim=512)
    store = build_vector_store(_chunks(), emb, qdrant_path=None, lane="offline")

    with pytest.raises(ValueError, match="unknown retrieval_mode"):
        search(store, "사업", top_k=1, retrieval_mode="magic")


def test_hybrid_search_requires_index_dir() -> None:
    emb = LexicalHashEmbeddings(dim=512)
    store = build_vector_store(_chunks(), emb, qdrant_path=None, lane="offline")

    with pytest.raises(ValueError, match="index_dir is required"):
        search(store, "사업", top_k=1, retrieval_mode=RETRIEVAL_HYBRID)


def test_hybrid_search_promotes_keyword_candidate(tmp_path: Path) -> None:
    chunks = [
        Chunk(
            chunk_id="doc:000:chunk:0",
            doc_id="doc:000",
            csv_row_id="000",
            text="범용 시스템 유지보수",
            metadata={"project_name": "일반 유지보수", "issuer": "테스트기관"},
        ),
        Chunk(
            chunk_id="doc:001:chunk:0",
            doc_id="doc:001",
            csv_row_id="001",
            text="AI LMS 추천 엔진 학습 분석",
            metadata={"project_name": "AI LMS 고도화", "issuer": "테스트기관"},
        ),
    ]
    emb = LexicalHashEmbeddings(dim=512)
    index_dir = tmp_path / "index"
    save_index(index_dir, {"embedding_provider": "offline"}, chunks)
    store = build_vector_store(chunks, emb, qdrant_path=None, lane="offline")

    results = search(
        store,
        "AI LMS 추천 엔진",
        top_k=1,
        retrieval_mode=RETRIEVAL_HYBRID,
        index_dir=index_dir,
    )

    assert results[0].chunk_id == "doc:001:chunk:0"
    assert results[0].score > 0
```

Append to `tests/test_rag_chain.py`:

```python
def test_answer_with_store_rejects_hybrid_without_index_dir() -> None:
    with pytest.raises(ValueError, match="index_dir is required"):
        answer_with_store(
            _store(),
            TemplateAnswerGenerator(),
            "한영대학교 학사정보시스템",
            retrieval_mode="hybrid",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --group dev python -m pytest tests/test_vector_index.py tests/test_rag_chain.py -q
```

Expected: FAIL because `retrieval_mode`, `RETRIEVAL_HYBRID`, and `RETRIEVAL_VECTOR` do not exist.

- [ ] **Step 3: Implement retrieval mode routing**

Modify `rfp_rag/vector_index.py`:

```python
RETRIEVAL_VECTOR = "vector"
RETRIEVAL_HYBRID = "hybrid"
RETRIEVAL_MODES = {RETRIEVAL_VECTOR, RETRIEVAL_HYBRID}
```

Replace `search` with:

```python
def _vector_search(store: QdrantVectorStore, query: str, top_k: int) -> list[SearchResult]:
    if top_k <= 0:
        return []
    pairs = store.similarity_search_with_score(query, k=top_k)
    results: list[SearchResult] = []
    for document, score in pairs:
        md = {k: v for k, v in document.metadata.items() if not k.startswith("_")}
        results.append(
            SearchResult(
                chunk_id=md.pop("chunk_id"),
                doc_id=md.pop("doc_id"),
                csv_row_id=md.pop("csv_row_id"),
                score=round(float(score), 8),
                text=document.page_content,
                metadata=md,
            )
        )
    results.sort(key=lambda item: (-item.score, item.doc_id, item.chunk_id))
    return results


def search(
    store: QdrantVectorStore,
    query: str,
    top_k: int = 5,
    *,
    retrieval_mode: str = RETRIEVAL_VECTOR,
    index_dir: Path | None = None,
) -> list[SearchResult]:
    if retrieval_mode not in RETRIEVAL_MODES:
        raise ValueError(f"unknown retrieval_mode {retrieval_mode!r}; expected one of {sorted(RETRIEVAL_MODES)}")
    if retrieval_mode == RETRIEVAL_VECTOR:
        return _vector_search(store, query, top_k=top_k)
    if index_dir is None:
        raise ValueError("index_dir is required for hybrid retrieval")

    from .hybrid_retrieval import BM25Index, fuse_ranked_results

    candidate_k = max(top_k * 4, 20)
    vector_results = _vector_search(store, query, top_k=candidate_k)
    bm25_results = BM25Index.from_index_dir(index_dir).search(query, top_k=candidate_k)
    return fuse_ranked_results(vector_results, bm25_results, top_k=top_k)
```

Modify `rfp_rag/rag_chain.py`:

```python
from .vector_index import RETRIEVAL_VECTOR, load_vector_store, search
```

Update `answer_with_store` signature:

```python
def answer_with_store(
    store: QdrantVectorStore,
    generator: AnswerGenerator,
    query: str,
    top_k: int = 5,
    min_score: float = DEFAULT_MIN_SCORE,
    *,
    retrieval_mode: str = RETRIEVAL_VECTOR,
    index_dir: Path | None = None,
) -> dict[str, Any]:
    results = search(store, query, top_k=top_k, retrieval_mode=retrieval_mode, index_dir=index_dir)
```

Update `answer_query` signature and final call:

```python
def answer_query(
    index_dir: Path | str,
    query: str,
    top_k: int = 5,
    min_score: float = DEFAULT_MIN_SCORE,
    provider: str | None = None,
    retrieval_mode: str = RETRIEVAL_VECTOR,
) -> dict[str, Any]:
    ...
    return answer_with_store(
        store,
        generator,
        query,
        top_k=top_k,
        min_score=min_score,
        retrieval_mode=retrieval_mode,
        index_dir=index_dir,
    )
```

- [ ] **Step 4: Run routing tests**

Run:

```bash
uv run --group dev python -m pytest tests/test_vector_index.py tests/test_rag_chain.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/vector_index.py rfp_rag/rag_chain.py tests/test_vector_index.py tests/test_rag_chain.py
git commit -m "feat: route vector and hybrid retrieval modes"
```

---

### Task 3: Evaluation and CLI Wiring

**Files:**
- Modify: `rfp_rag/evaluate.py`
- Modify: `rfp_rag/ask.py`
- Test: `tests/test_evaluate_report.py`

- [ ] **Step 1: Add failing evaluation metric test**

Modify `tests/test_evaluate_report.py` in `test_evaluate_index_writes_offline_contract_artifacts` so the `evaluate_index(...)` call includes:

```python
retrieval_mode="hybrid",
```

Add assertions after `metrics = evaluate_index(...)`:

```python
assert metrics["retrieval_mode"] == "hybrid"
saved_metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
assert saved_metrics["retrieval_mode"] == "hybrid"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --group dev python -m pytest tests/test_evaluate_report.py -q
```

Expected: FAIL because `evaluate_index` does not accept `retrieval_mode`.

- [ ] **Step 3: Wire retrieval mode into evaluation**

Modify `rfp_rag/evaluate.py`:

```python
from .vector_index import RETRIEVAL_VECTOR, RETRIEVAL_MODES
```

Update `evaluate_index` signature:

```python
def evaluate_index(
    data_path: Path | str,
    index_dir: Path | str,
    out_dir: Path | str,
    provider: str = "fake_offline",
    top_k: int = 5,
    max_docs: int = 10,
    min_score: float = 0.05,
    retrieval_mode: str = RETRIEVAL_VECTOR,
) -> dict[str, Any]:
```

Pass retrieval mode into `answer_query`:

```python
response = answer_query(
    index_dir,
    record["query"],
    top_k=top_k,
    min_score=min_score,
    retrieval_mode=retrieval_mode,
)
```

Add to metrics:

```python
"retrieval_mode": retrieval_mode,
```

Update CLI parser:

```python
parser.add_argument("--retrieval-mode", choices=sorted(RETRIEVAL_MODES), default=RETRIEVAL_VECTOR)
```

Pass `retrieval_mode=args.retrieval_mode` into `evaluate_index(...)`.

- [ ] **Step 4: Wire retrieval mode into ask CLI**

Modify `rfp_rag/ask.py`:

```python
from .vector_index import RETRIEVAL_MODES, RETRIEVAL_VECTOR
```

Add parser argument:

```python
parser.add_argument("--retrieval-mode", choices=sorted(RETRIEVAL_MODES), default=RETRIEVAL_VECTOR)
```

Pass into `answer_query`:

```python
retrieval_mode=args.retrieval_mode,
```

- [ ] **Step 5: Run evaluation tests**

Run:

```bash
uv run --group dev python -m pytest tests/test_evaluate_report.py tests/test_qa.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add rfp_rag/evaluate.py rfp_rag/ask.py tests/test_evaluate_report.py
git commit -m "feat: expose retrieval mode in evaluation"
```

---

### Task 4: Offline Hybrid Evidence and Documentation

**Files:**
- Modify: `README.md`
- Modify: `REPORT.md`

- [ ] **Step 1: Run full credential-free tests**

Run:

```bash
uv run --group dev python -m pytest -m "not real" -q
```

Expected: PASS.

- [ ] **Step 2: Ensure offline vector index exists**

Run:

```bash
uv run --group dev python -m rfp_rag.build_index \
  --data data/data_list.csv --files data/files \
  --out artifacts/index --chunk-size 500 --chunk-overlap 80 --embedding-provider offline
```

Expected: command exits 0 and prints a manifest with `"embedding_provider": "offline"`.

- [ ] **Step 3: Run offline vector baseline evaluation**

Run:

```bash
uv run --group dev python -m rfp_rag.evaluate \
  --data data/data_list.csv --index artifacts/index \
  --out artifacts/eval_vector_offline \
  --provider offline --top-k 5 --min-score 0.15 --retrieval-mode vector
```

Expected: command exits 0 and prints metrics with `"retrieval_mode": "vector"`.

- [ ] **Step 4: Run offline hybrid evaluation**

Run:

```bash
uv run --group dev python -m rfp_rag.evaluate \
  --data data/data_list.csv --index artifacts/index \
  --out artifacts/eval_hybrid_offline \
  --provider offline --top-k 5 --min-score 0.15 --retrieval-mode hybrid
```

Expected: command exits 0 and prints metrics with `"retrieval_mode": "hybrid"`.

- [ ] **Step 5: Extract comparison metrics**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path

rows = []
for label, path in [
    ("vector", Path("artifacts/eval_vector_offline/metrics.json")),
    ("hybrid", Path("artifacts/eval_hybrid_offline/metrics.json")),
]:
    metrics = json.loads(path.read_text(encoding="utf-8"))
    aggregate = metrics["aggregate"]
    rows.append({
        "mode": label,
        "retrieval_mode": metrics["retrieval_mode"],
        "recall@5": aggregate.get("recall@5"),
        "mrr": aggregate.get("mrr"),
        "metadata_exact_match": aggregate.get("metadata_exact_match"),
        "citation_presence": aggregate.get("citation_presence"),
        "abstention_pass": aggregate.get("abstention_pass"),
        "evaluation_valid": metrics["evaluation_valid"],
        "error_rate": metrics["error_rate"],
    })
print(json.dumps(rows, ensure_ascii=False, indent=2))
PY
```

Expected: JSON containing both modes and comparable aggregate metrics.

- [ ] **Step 6: Update README**

Add under the evaluation command section:

```markdown
### Retrieval mode

`--retrieval-mode vector` is the default. `--retrieval-mode hybrid` fuses Qdrant vector candidates with local BM25 candidates from `chunks.jsonl` using reciprocal-rank fusion.

```bash
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index \
  --out artifacts/eval_hybrid_offline --provider offline --top-k 5 \
  --min-score 0.15 --retrieval-mode hybrid
```

Hybrid retrieval is an experiment lane. It does not replace the `real_openai` quality gate.
```

- [ ] **Step 7: Generate the REPORT comparison table**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path

print("| mode | recall@5 | mrr | metadata_exact_match | citation_presence | abstention_pass | evaluation_valid | error_rate |")
print("|---|---:|---:|---:|---:|---:|---|---:|")
for label, path in [
    ("vector", Path("artifacts/eval_vector_offline/metrics.json")),
    ("hybrid", Path("artifacts/eval_hybrid_offline/metrics.json")),
]:
    metrics = json.loads(path.read_text(encoding="utf-8"))
    aggregate = metrics["aggregate"]
    print(
        "| {mode} | {recall5} | {mrr} | {metadata} | {citation} | {abstention} | {valid} | {error} |".format(
            mode=label,
            recall5=aggregate.get("recall@5"),
            mrr=aggregate.get("mrr"),
            metadata=aggregate.get("metadata_exact_match"),
            citation=aggregate.get("citation_presence"),
            abstention=aggregate.get("abstention_pass"),
            valid=str(metrics["evaluation_valid"]).lower(),
            error=metrics["error_rate"],
        )
    )
PY
```

Expected: a two-row Markdown table for vector and hybrid.

- [ ] **Step 8: Update REPORT with the generated table**

Append a section near the open lane or experiment sections:

```markdown
### 10-16. Hybrid Retrieval Experiment

BM25 + vector reciprocal-rank fusion을 `--retrieval-mode hybrid`로 추가했다. 기본값은 기존과 동일한 `vector`이며, hybrid는 실험 레인이다.

재현 커맨드:

```bash
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index \
  --out artifacts/eval_vector_offline --provider offline --top-k 5 \
  --min-score 0.15 --retrieval-mode vector
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index \
  --out artifacts/eval_hybrid_offline --provider offline --top-k 5 \
  --min-score 0.15 --retrieval-mode hybrid
```

이 결과는 offline contract 기반 비교이며, 최종 RAG 품질 주장은 계속 `real_openai` lane에만 귀속된다.
```

Insert the Markdown table printed by Step 7 between the opening paragraph and `재현 커맨드:` before committing.

- [ ] **Step 9: Run docs consistency checks**

Run:

```bash
uv run --group dev python -m rfp_rag.report_check --eval artifacts/eval --readme README.md
rg -n "retrieval-mode hybrid|Hybrid Retrieval|eval_hybrid_offline" README.md REPORT.md
```

Expected: report check returns `"ok": true`; ripgrep finds the new docs.

- [ ] **Step 10: Commit docs and evidence references**

```bash
git add README.md REPORT.md
git commit -m "docs: record hybrid retrieval experiment"
```

---

### Task 5: Final Verification

**Files:**
- No source edits expected.

- [ ] **Step 1: Run full test suite without real tests**

Run:

```bash
uv run --group dev python -m pytest -m "not real" -q
```

Expected: PASS.

- [ ] **Step 2: Check git status and log**

Run:

```bash
git status --short
git log --oneline -5
```

Expected: only ignored artifact/cache files are untracked; recent commits include the hybrid retrieval commits.

- [ ] **Step 3: Push branch**

Run:

```bash
git push -u origin feature/hybrid-retrieval
```

Expected: branch pushed to origin.

---

## Self-Review

- Spec coverage: BM25 helper, fusion, retrieval mode routing, evaluation metrics, CLI flag, docs, and offline evidence are all covered.
- Placeholder scan: no unfinished values are left in the committed plan; Task 4 generates the final REPORT table from metrics files.
- Type consistency: `retrieval_mode` uses `RETRIEVAL_VECTOR`, `RETRIEVAL_HYBRID`, and `RETRIEVAL_MODES`; all callers pass a string mode through the same name.
- Scope check: reranker, UI, new embeddings, and agent behavior remain excluded.
