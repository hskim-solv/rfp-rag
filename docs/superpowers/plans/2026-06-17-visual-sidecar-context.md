# Visual Sidecar Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Attach gate-passing visual candidate facts to RAG answer context as a sidecar without changing text retrieval ranking or parsed source chunks.

**Architecture:** Add a small `visual_sidecar` module that loads candidate facts only when the visual candidate gate passes, groups facts by `doc_id`, and returns copied `SearchResult` objects with `metadata["visual_evidence"]`. `providers.chunk_context_block` renders those facts under a separate `시각근거:` label, and `rag_chain.answer_with_store` optionally attaches the sidecar after retrieval/reranking and before generation.

**Tech Stack:** Python 3.11+, existing JSONL artifact style, `SearchResult` metadata, pytest, ruff.

---

### Task 1: Visual Sidecar Loader

**Files:**
- Create: `rfp_rag/visual_sidecar.py`
- Test: `tests/test_visual_sidecar.py`

- [ ] **Step 1: Write failing tests**

Create tests that verify:

```python
index = load_visual_sidecar(candidate_path, gate_path)
assert index.by_doc_id["doc:040"][0]["page"] == 10
assert index.by_doc_id["doc:040"][0]["visual_type"] == "requirements_table"
```

Also test that `load_visual_sidecar(candidate_path, failed_gate_path)` raises `ValueError`.

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run python -m pytest tests/test_visual_sidecar.py -q
```

Expected: import failure for missing `rfp_rag.visual_sidecar`.

- [ ] **Step 3: Implement loader**

Implement:

```python
@dataclass(frozen=True)
class VisualEvidenceIndex:
    by_doc_id: dict[str, list[dict[str, Any]]]

def load_visual_sidecar(candidate_path: Path | str, gate_summary_path: Path | str | None = None) -> VisualEvidenceIndex:
    ...
```

Parse `record_id` shaped like `doc:040:p10:requirements_table` into `doc_id`, `page`, and `visual_type`.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
uv run python -m pytest tests/test_visual_sidecar.py -q
```

Expected: all tests pass.

### Task 2: Attach Evidence To Retrieved Results

**Files:**
- Modify: `rfp_rag/visual_sidecar.py`
- Test: `tests/test_visual_sidecar.py`

- [ ] **Step 1: Write failing test**

Add a test that builds a `SearchResult(doc_id="doc:040")`, attaches a sidecar index, and asserts:

```python
attached[0].metadata["visual_evidence"][0]["record_id"] == "doc:040:p10:requirements_table"
```

Also assert the original result metadata is unchanged.

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run python -m pytest tests/test_visual_sidecar.py -q
```

Expected: missing `attach_visual_evidence` failure.

- [ ] **Step 3: Implement attachment**

Implement:

```python
def attach_visual_evidence(results: Iterable[SearchResult], index: VisualEvidenceIndex | None, max_per_result: int = 5) -> list[SearchResult]:
    ...
```

Return copied `SearchResult` objects. Do not mutate the input results.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
uv run python -m pytest tests/test_visual_sidecar.py -q
```

Expected: all tests pass.

### Task 3: Render Visual Evidence In Prompt Context

**Files:**
- Modify: `rfp_rag/providers.py`
- Test: `tests/test_providers.py`

- [ ] **Step 1: Write failing test**

Create a `SearchResult` with `metadata["visual_evidence"]` and assert `chunk_context_block(result)` contains:

```text
시각근거:
- doc:040 p10 requirements_table: Requirements table is present on the selected page
```

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run python -m pytest tests/test_providers.py::test_chunk_context_block_renders_visual_evidence -q
```

Expected: assertion failure because visual evidence is not rendered.

- [ ] **Step 3: Implement rendering**

Append visual evidence lines after page metadata and before body text. Keep `본문:` unchanged.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
uv run python -m pytest tests/test_providers.py::test_chunk_context_block_renders_visual_evidence -q
```

Expected: test passes.

### Task 4: Wire Sidecar Into RAG Answer Flow

**Files:**
- Modify: `rfp_rag/rag_chain.py`
- Modify: `rfp_rag/ask.py`
- Test: `tests/test_rag_chain.py`

- [ ] **Step 1: Write failing test**

Add a test that passes a `VisualEvidenceIndex` into `answer_with_store` and asserts:

```python
assert response["sources"][0]["visual_evidence"][0]["record_id"] == "doc:000:p3:gantt_schedule"
assert "시각근거:" in response["source_texts"][0]
```

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run python -m pytest tests/test_rag_chain.py::test_answer_with_store_attaches_visual_sidecar_context -q
```

Expected: unexpected keyword argument or missing visual evidence.

- [ ] **Step 3: Implement wiring**

Add optional `visual_evidence_index` to `answer_with_store` and optional CLI args to `ask.py`:

```text
--visual-candidates artifacts/visual_tesseract_candidate_expanded/candidate_facts.jsonl
--visual-gate artifacts/visual_tesseract_candidate_expanded_gate/summary.json
```

Load the sidecar in `answer_query` only when `--visual-candidates` is passed.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
uv run python -m pytest tests/test_rag_chain.py::test_answer_with_store_attaches_visual_sidecar_context -q
```

Expected: test passes.

### Task 5: Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `REPORT.md`

- [ ] **Step 1: Document command shape**

Document:

```bash
python3 -m rfp_rag.ask \
  --index artifacts/index \
  --query "..." \
  --visual-candidates artifacts/visual_tesseract_candidate_expanded/candidate_facts.jsonl \
  --visual-gate artifacts/visual_tesseract_candidate_expanded_gate/summary.json
```

- [ ] **Step 2: Run focused verification**

Run:

```bash
uv run python -m pytest tests/test_visual_sidecar.py tests/test_providers.py tests/test_rag_chain.py -q
uv run ruff format --check rfp_rag/visual_sidecar.py rfp_rag/providers.py rfp_rag/rag_chain.py rfp_rag/ask.py tests/test_visual_sidecar.py tests/test_providers.py tests/test_rag_chain.py
uv run ruff check rfp_rag/visual_sidecar.py rfp_rag/providers.py rfp_rag/rag_chain.py rfp_rag/ask.py tests/test_visual_sidecar.py tests/test_providers.py tests/test_rag_chain.py
uv run python -m rfp_rag.report_check --eval artifacts/eval --readme README.md
```

- [ ] **Step 3: Run offline gate**

Run:

```bash
env -u OPENAI_API_KEY -u LANGFUSE_PUBLIC_KEY -u LANGFUSE_SECRET_KEY uv run python -m pytest -p no:cacheprovider -m "not real" --tb=short -q
```

- [ ] **Step 4: Commit, push, PR, merge**

Use the existing squash PR flow.
