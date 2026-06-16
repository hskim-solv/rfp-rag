# Visual Tesseract Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a credential-free Tesseract OCR visual candidate lane and compare it against the reviewer gold set.

**Architecture:** Add a focused `visual_tesseract_candidate.py` module with pure candidate-building logic plus a thin CLI wrapper. Production execution renders page PPMs with `pdftoppm`, streams bytes to Tesseract `stdin`, writes candidate/observation/summary artifacts, and reuses `run_visual_gold_eval`.

**Tech Stack:** Python 3.11+, `subprocess`, JSONL, local `pdftoppm`, local `tesseract`, pytest, ruff.

---

### Task 1: Candidate Builder

**Files:**
- Create: `rfp_rag/visual_tesseract_candidate.py`
- Test: `tests/test_visual_tesseract_candidate.py`

- [x] **Step 1: Write failing pure-builder tests**

Cover visual-type keyword matching, fact type mapping, reviewed-record filtering,
and no-candidate behavior when OCR text is empty.

- [x] **Step 2: Verify RED**

Run:

```bash
uv run python -m pytest tests/test_visual_tesseract_candidate.py -q
```

Expected: import failure because `rfp_rag.visual_tesseract_candidate` does not exist.

- [x] **Step 3: Implement pure candidate builder**

Implement `build_visual_tesseract_candidates(records, ocr_text_by_record)`.

- [x] **Step 4: Verify GREEN**

Run:

```bash
uv run python -m pytest tests/test_visual_tesseract_candidate.py -q
```

Expected: tests pass.

### Task 2: CLI and Artifact Writer

**Files:**
- Modify: `rfp_rag/visual_tesseract_candidate.py`
- Create: `rfp_rag/run_visual_tesseract_candidate.py`
- Test: `tests/test_visual_tesseract_candidate.py`

- [x] **Step 1: Add failing artifact/CLI tests**

Use a test-only `--ocr-text` JSONL fixture to avoid external OCR in unit tests.
Assert `candidate_facts.jsonl`, `observations.jsonl`, and `summary.json` are written.

- [x] **Step 2: Verify RED**

Run:

```bash
uv run python -m pytest tests/test_visual_tesseract_candidate.py -q
```

Expected: CLI/import failure.

- [x] **Step 3: Implement run function and CLI**

Implement `run_visual_tesseract_candidate()` and CLI args:

- `--records`
- `--out`
- `--ocr-text` optional fixture path
- `--dpi` default `150`
- `--lang` default `kor+eng`
- `--psm` default `11`
- `--timeout-seconds` default `20`

- [x] **Step 4: Verify GREEN**

Run:

```bash
ruff format rfp_rag/visual_tesseract_candidate.py rfp_rag/run_visual_tesseract_candidate.py tests/test_visual_tesseract_candidate.py
ruff check rfp_rag/visual_tesseract_candidate.py rfp_rag/run_visual_tesseract_candidate.py tests/test_visual_tesseract_candidate.py
uv run python -m pytest tests/test_visual_tesseract_candidate.py -q
```

Expected: lint and tests pass.

### Task 3: Real Local Candidate Run and Documentation

**Files:**
- Modify: `README.md`
- Modify: `REPORT.md`

- [x] **Step 1: Generate real local OCR candidate artifacts**

Run:

```bash
uv run python -m rfp_rag.run_visual_tesseract_candidate \
  --records artifacts/visual_structure/records.jsonl \
  --out artifacts/visual_tesseract_candidate \
  --dpi 120 \
  --timeout-seconds 15
```

- [x] **Step 2: Evaluate against visual gold**

Run:

```bash
uv run python -m rfp_rag.run_visual_gold_eval \
  --gold docs/evidence/visual-structure-review-facts.seed.jsonl \
  --candidate artifacts/visual_tesseract_candidate/candidate_facts.jsonl \
  --out artifacts/visual_tesseract_candidate_eval
```

- [x] **Step 3: Document commands and metrics**

Add the command and resulting metrics to `README.md` and `REPORT.md`.

- [x] **Step 4: Verify focused and offline checks**

Run:

```bash
uv run python -m pytest tests/test_visual_tesseract_candidate.py tests/test_visual_gold_eval.py -q
uv run python -m rfp_rag.report_check --eval artifacts/eval --readme README.md
env -u OPENAI_API_KEY -u LANGFUSE_PUBLIC_KEY -u LANGFUSE_SECRET_KEY \
  uv run python -m pytest -p no:cacheprovider -m "not real" --tb=short -q
```
