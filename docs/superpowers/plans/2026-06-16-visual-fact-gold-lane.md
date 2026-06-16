# Visual Fact Gold Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a credential-free reviewer fact lane that turns visual-structure records into a gold set for later OCR/VLM comparison.

**Architecture:** Add a focused `visual_facts.py` module for validation/merge logic and a thin CLI wrapper. The lane reads existing visual records plus reviewer fact JSONL, writes reviewed records and summary artifacts, and never mutates canonical `artifacts/visual_structure` in place.

**Tech Stack:** Python 3.11+, JSONL artifacts, pytest, ruff.

---

### Task 1: Reviewer Fact Merge Core

**Files:**
- Create: `rfp_rag/visual_facts.py`
- Test: `tests/test_visual_facts.py`

- [x] **Step 1: Write failing tests**

Add tests that cover accepted fact merge, rejected fact counting, unknown record
rejection, invalid field rejection, and incompatible fact type rejection.

- [x] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_visual_facts.py -q
```

Expected: import failure because `rfp_rag.visual_facts` does not exist.

- [x] **Step 3: Implement minimal core**

Implement `load_jsonl`, `merge_visual_facts`, `write_visual_fact_artifacts`, and
`run_visual_fact_review` with strict validation.

- [x] **Step 4: Run tests to verify pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_visual_facts.py -q
```

Expected: all tests pass.

### Task 2: CLI Wrapper

**Files:**
- Create: `rfp_rag/run_visual_fact_review.py`
- Test: `tests/test_visual_facts.py`

- [x] **Step 1: Write failing CLI test**

Add a test invoking `main()` with `--records`, `--facts`, and `--out`.

- [x] **Step 2: Run CLI test to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_visual_facts.py::test_run_visual_fact_review_cli_writes_outputs -q
```

Expected: import failure because the CLI module does not exist.

- [x] **Step 3: Implement CLI**

Create an argparse wrapper that prints summary JSON.

- [x] **Step 4: Run CLI test to verify pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_visual_facts.py::test_run_visual_fact_review_cli_writes_outputs -q
```

Expected: pass.

### Task 3: Documentation and Verification

**Files:**
- Modify: `README.md`
- Modify: `REPORT.md`

- [x] **Step 1: Document command and policy**

Add the reviewer fact merge command and explain that OCR/VLM remains deferred
until compared against this gold set.

- [x] **Step 2: Run focused checks**

Run:

```bash
ruff format rfp_rag/visual_facts.py rfp_rag/run_visual_fact_review.py tests/test_visual_facts.py
ruff check rfp_rag/visual_facts.py rfp_rag/run_visual_fact_review.py tests/test_visual_facts.py
.venv/bin/python -m pytest tests/test_visual_facts.py -q
```

Expected: all pass.

- [x] **Step 3: Run offline smoke**

Run:

```bash
.venv/bin/python -m rfp_rag.report_check --eval artifacts/eval --readme README.md
env -u OPENAI_API_KEY -u LANGFUSE_PUBLIC_KEY -u LANGFUSE_SECRET_KEY .venv/bin/python -m pytest -p no:cacheprovider -m "not real" --tb=short -q
```

Expected: report_check ok and offline tests pass.
