# Visual Local Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a credential-free deterministic visual candidate baseline before OCR/VLM adoption.

**Architecture:** Add `visual_local_baseline.py` for record-to-candidate conversion and a thin CLI wrapper. The lane writes candidate JSONL and summary artifacts, then the existing visual gold evaluator scores those candidates.

**Tech Stack:** Python 3.11+, JSONL, pytest, ruff.

---

### Task 1: Candidate Baseline Core

**Files:**
- Create: `rfp_rag/visual_local_baseline.py`
- Test: `tests/test_visual_local_baseline.py`

- [x] **Step 1: Write failing tests**

Cover field selection, reviewed-record filtering, JSONL artifact writing, and
summary counts.

- [x] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_visual_local_baseline.py -q
```

Expected: import failure because `rfp_rag.visual_local_baseline` does not exist.

- [x] **Step 3: Implement core**

Implement `build_visual_local_candidates()` and `run_visual_local_baseline()`.

- [x] **Step 4: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_visual_local_baseline.py -q
```

Expected: tests pass.

### Task 2: CLI and Docs

**Files:**
- Create: `rfp_rag/run_visual_local_baseline.py`
- Modify: `README.md`
- Modify: `REPORT.md`

- [x] **Step 1: Add CLI test**

Add a test invoking `main()` with `--records` and `--out`.

- [x] **Step 2: Implement CLI**

Create argparse wrapper that prints summary JSON.

- [x] **Step 3: Document command**

Document baseline generation and evaluation commands.

- [x] **Step 4: Verify**

Run:

```bash
ruff format rfp_rag/visual_local_baseline.py rfp_rag/run_visual_local_baseline.py tests/test_visual_local_baseline.py
ruff check rfp_rag/visual_local_baseline.py rfp_rag/run_visual_local_baseline.py tests/test_visual_local_baseline.py
.venv/bin/python -m pytest tests/test_visual_local_baseline.py tests/test_visual_gold_eval.py -q
```
