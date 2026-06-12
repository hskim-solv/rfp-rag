# Open Lane Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close `rfp-rag-open-v1` by producing open-lane evidence, calibrating the lane-specific retrieval cutoff, and documenting that the lane is an iteration signal rather than quality-gate evidence.

**Architecture:** Keep the existing lane architecture intact. Use the already implemented `open` provider, `open_contract()`, `artifacts/index_open`, and `artifacts/eval_open`; make only the smallest code changes needed if a preflight or documentation gap is discovered. Documentation updates in `README.md` and `REPORT.md` are the primary expected edits.

**Tech Stack:** Python 3.11, pytest, LangChain OpenAI-compatible clients, Ollama-compatible embeddings (`bge-m3`), DeepSeek/OpenAI-compatible generation, local JSON/JSONL evaluation artifacts.

---

## File Structure

- Modify: `README.md`
  - Update the Open lane section with the calibrated `--min-score`, exact closeout command, and interpretation.
- Modify: `REPORT.md`
  - Add the open lane closeout evidence section with backend, metrics, score-distribution rationale, and limitations.
- Possibly modify: `rfp_rag/contracts.py`
  - Only if the final calibrated command should be embedded in `OPEN_REQUIRED_COMMANDS`.
- Possibly modify: `tests/test_evaluate_report.py` or `tests/test_providers.py`
  - Only if the closeout requires a small guard or contract assertion that is missing.
- Generated or updated artifacts, not necessarily committed unless repository policy already tracks them:
  - `artifacts/index_open/`
  - `artifacts/eval_open/metrics.json`
  - `artifacts/eval_open/predictions.jsonl`
  - `artifacts/eval_open/report.md`
  - `artifacts/eval_open/contract.json`

Do not include the existing untracked `uv.lock` unless the user separately decides to track it.

## Task 1: Preflight Current State

**Files:**
- Read: `README.md`
- Read: `REPORT.md`
- Read: `rfp_rag/contracts.py`
- Read: `rfp_rag/providers.py`
- Read: `rfp_rag/evaluate.py`

- [ ] **Step 1: Confirm worktree state**

Run:

```bash
git status --short --branch
```

Expected: branch is `feature/open-lane`; `uv.lock` may appear as untracked. Do not stage `uv.lock`.

- [ ] **Step 2: Confirm open lane commands already exist**

Run:

```bash
rg -n "rfp-rag-open-v1|embedding-provider open|provider open|RFP_OPEN|DEEPSEEK|eval_open|index_open" README.md REPORT.md rfp_rag/contracts.py rfp_rag/providers.py rfp_rag/evaluate.py tests
```

Expected: `README.md`, `REPORT.md`, `rfp_rag/contracts.py`, and `rfp_rag/providers.py` all already mention the open lane.

- [ ] **Step 3: Confirm credential-free test target**

Run:

```bash
python3 -m pytest -m "not real" tests/test_providers.py tests/test_reaggregate.py tests/test_evaluate_report.py -q
```

Expected: PASS. If this fails, stop and investigate the failing test before touching open-lane docs.

## Task 2: Check Open Lane Runtime Prerequisites

**Files:**
- No source edits expected.

- [ ] **Step 1: Check Ollama embedding backend**

Run:

```bash
curl -fsS http://localhost:11434/api/tags | python3 -m json.tool | sed -n '1,80p'
```

Expected if available: JSON containing installed Ollama models. `bge-m3` should be present for the default open embedding path.

Expected if unavailable: curl connection failure. If unavailable, document the missing local embedding service in `REPORT.md` and do not treat it as an offline regression.

- [ ] **Step 2: Check generation backend selection**

Run:

```bash
python3 - <<'PY'
import os

base_url = os.environ.get("RFP_OPEN_BASE_URL", "https://api.deepseek.com")
model = os.environ.get("RFP_OPEN_MODEL", "deepseek-v4-flash")
has_remote_key = bool(os.environ.get("RFP_OPEN_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"))
is_local = base_url.startswith("http://localhost") or base_url.startswith("http://127.0.0.1")

print(f"RFP_OPEN_BASE_URL={base_url}")
print(f"RFP_OPEN_MODEL={model}")
print(f"remote_key_available={has_remote_key}")
print(f"local_backend={is_local}")
if not is_local and not has_remote_key:
    raise SystemExit("missing RFP_OPEN_API_KEY or DEEPSEEK_API_KEY for remote open generation")
PY
```

Expected if available: printed backend settings and exit code 0.

Expected if unavailable: exits with `missing RFP_OPEN_API_KEY or DEEPSEEK_API_KEY for remote open generation`. In that case, either set a key, switch to a local OpenAI-compatible backend with `RFP_OPEN_BASE_URL=http://localhost:11434/v1`, or document the missing prerequisite.

- [ ] **Step 3: Decide execution path**

If both embedding and generation prerequisites are available, proceed to Task 3.

If either prerequisite is unavailable, skip Task 3 and Task 4, then complete Task 5 with an explicit limitation section stating the exact missing prerequisite. Still run Task 6 credential-free verification.

## Task 3: Produce First Open Lane Evidence

**Files:**
- Generate or update: `artifacts/index_open/`
- Generate or update: `artifacts/eval_open/`

- [ ] **Step 1: Build the open index**

Run:

```bash
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files \
  --out artifacts/index_open --chunk-size 500 --chunk-overlap 80 --embedding-provider open
```

Expected: command exits 0 and writes `artifacts/index_open/manifest.json`, `artifacts/index_open/chunks.jsonl`, and `artifacts/index_open/qdrant/`.

- [ ] **Step 2: Run first open evaluation without a calibrated cutoff**

Run:

```bash
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_open \
  --out artifacts/eval_open --provider open --top-k 5
```

Expected: command exits 0 and writes `artifacts/eval_open/metrics.json`, `predictions.jsonl`, `report.md`, and `contract.json`.

- [ ] **Step 3: Print first-run metrics**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path

metrics = json.loads(Path("artifacts/eval_open/metrics.json").read_text(encoding="utf-8"))
print("provider_lane:", metrics["provider_lane"])
print("min_score:", metrics["min_score"])
print("error_rate:", metrics["error_rate"])
print("evaluation_valid:", metrics["evaluation_valid"])
print("rag_quality_complete:", metrics["rag_quality_complete"])
print("aggregate:")
for key, value in metrics["aggregate"].items():
    print(f"  {key}: {value}")
print("score_distribution:")
for key, values in metrics["score_distribution"].items():
    print(f"  {key}: count={len(values)} min={min(values) if values else None} max={max(values) if values else None}")
PY
```

Expected: `provider_lane: open` and `rag_quality_complete: False`.

## Task 4: Calibrate Open Lane Min Score

**Files:**
- Update: `artifacts/eval_open/`
- Possibly modify: `rfp_rag/contracts.py`

- [ ] **Step 1: Compute cutoff recommendation from score distribution**

Run:

```bash
OPEN_MIN_SCORE="$(python3 - <<'PY'
import json
from pathlib import Path

metrics = json.loads(Path("artifacts/eval_open/metrics.json").read_text(encoding="utf-8"))
dist = metrics["score_distribution"]
in_domain = list(dist.get("in_domain_top_scores") or [])
abstention = list(dist.get("abstention_top_scores") or [])

if not in_domain or not abstention:
    raise SystemExit("inconclusive: missing in-domain or abstention top scores")

in_min = min(in_domain)
abst_max = max(abstention)
if abst_max >= in_min:
    print("INCONCLUSIVE")
else:
    # Conservative midpoint, rounded down to two decimals so minor score drift does not
    # accidentally exclude the weakest in-domain query.
    raw = (abst_max + in_min) / 2
    cutoff = max(0.0, int(raw * 100) / 100)
    print(f"{cutoff:.2f}")
PY
)"
echo "$OPEN_MIN_SCORE"
```

Expected if separable: a numeric value such as `0.47`.

Expected if not separable: `INCONCLUSIVE` or an explicit `inconclusive:` error. If inconclusive, do not force a cutoff; document the overlap in `REPORT.md`.

- [ ] **Step 2: Re-run evaluation with calibrated cutoff when available**

Run only if `OPEN_MIN_SCORE` is numeric:

```bash
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_open \
  --out artifacts/eval_open --provider open --top-k 5 --min-score "$OPEN_MIN_SCORE"
```

Expected: command exits 0; `artifacts/eval_open/metrics.json` records `"min_score": <numeric value>` and still records `"rag_quality_complete": false`.

- [ ] **Step 3: Reprint final metrics**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path

metrics = json.loads(Path("artifacts/eval_open/metrics.json").read_text(encoding="utf-8"))
print(json.dumps({
    "provider_lane": metrics["provider_lane"],
    "top_k": metrics["top_k"],
    "min_score": metrics["min_score"],
    "error_rate": metrics["error_rate"],
    "evaluation_valid": metrics["evaluation_valid"],
    "rag_quality_complete": metrics["rag_quality_complete"],
    "aggregate": metrics["aggregate"],
    "score_distribution": metrics["score_distribution"],
}, ensure_ascii=False, indent=2, sort_keys=True))
PY
```

Expected: final metrics ready to paste into `REPORT.md`.

- [ ] **Step 4: Update open contract command only if cutoff is calibrated**

If `OPEN_MIN_SCORE` is numeric, modify `rfp_rag/contracts.py` so `OPEN_REQUIRED_COMMANDS` includes the calibrated `--min-score`.

Example for `0.47`:

```python
OPEN_REQUIRED_COMMANDS = [
    "python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index_open --chunk-size 500 --chunk-overlap 80 --embedding-provider open",
    "python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_open --out artifacts/eval_open --provider open --top-k 5 --min-score 0.47",
]
```

If calibration is inconclusive or no run was possible, leave `OPEN_REQUIRED_COMMANDS` unchanged and explain the reason in `REPORT.md`.

## Task 5: Update README and REPORT

**Files:**
- Modify: `README.md`
- Modify: `REPORT.md`
- Possibly modify: `rfp_rag/contracts.py`

- [ ] **Step 1: Update README Open lane command**

If a numeric cutoff was calibrated, update the Open lane evaluate command in `README.md` to include it.

Example for `0.47`:

```bash
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_open \
  --out artifacts/eval_open --provider open --top-k 5 --min-score 0.47
```

If calibration was inconclusive or skipped, keep the command without `--min-score` and add this sentence under the command:

```markdown
- `--min-score`는 첫 성공 런의 `score_distribution`에서 in-domain top score와 abstention top score가 분리될 때만 고정합니다. 분리가 없거나 백엔드가 준비되지 않은 경우 open lane은 cutoff 미확정 상태로 남깁니다.
```

- [ ] **Step 2: Update README interpretation**

Ensure the Open lane section includes this wording:

```markdown
**게이트 증거가 아닙니다** — judge 점수를 이터레이션 신호로만 쓰고,
`rag_quality_complete`는 real lane에서만 판정합니다.
```

Expected: this wording is already present or appears once after the edit.

- [ ] **Step 3: Add REPORT closeout section**

Append a new section near the current open lane discussion in `REPORT.md` with this structure:

```markdown
## 15. Open Lane Closeout

`rfp-rag-open-v1`은 저비용 이터레이션 레인이다. 이 레인은 검색·생성 실험의 신호를 제공하지만, 최종 품질 게이트는 아니다. `rag_quality_complete`는 계속 `rfp-rag-real-v2`에서만 판정한다.

### 15-1. 실행 환경

| 항목 | 값 |
|---|---|
| embedding backend | Ollama-compatible `bge-m3` |
| generation backend | DeepSeek/OpenAI-compatible backend or documented local substitute |
| judge backend | existing judge configuration |
| output | `artifacts/eval_open` |

### 15-2. 결과

| 지표 | 값 |
|---|---:|
| min_score | final value from `artifacts/eval_open/metrics.json`, or `미확정` |
| error_rate | final value from metrics |
| evaluation_valid | final value from metrics |
| recall@5 | final value from `aggregate.recall@5`, or `미측정` |
| citation_validity | final value from `aggregate.citation_validity`, or `미측정` |
| faithfulness | final value from `aggregate.faithfulness`, or `미측정` |
| answer_relevancy | final value from `aggregate.answer_relevancy`, or `미측정` |
| rag_quality_complete | `false` |

### 15-3. min_score 보정

`score_distribution`의 in-domain top score와 abstention top score를 비교해 open lane 전용 cutoff를 정했다. 두 분포가 겹치면 cutoff를 고정하지 않고, open lane은 cutoff 미확정 상태로 둔다.

### 15-4. 해석

open lane 결과는 real lane gate를 대체하지 않는다. 이후 hybrid retrieval, reranking, 모델 비교 실험은 이 값을 baseline으로 삼되, 최종 품질 주장은 `artifacts/eval_real`의 real lane 결과로만 한다.
```

Replace the metric values with exact values from Task 4 Step 3. If no run was possible, replace the execution environment and result text with the exact missing prerequisite from Task 2.

- [ ] **Step 4: Keep FastMCP out of the implementation**

Verify that `README.md` and `REPORT.md` do not introduce FastMCP as part of this closeout:

```bash
rg -n "FastMCP|MCP" README.md REPORT.md docs/superpowers/specs/2026-06-12-open-lane-closeout-design.md
```

Expected: FastMCP appears only in the design spec's future note, not as an open lane implementation requirement.

## Task 6: Final Verification and Commit

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
python3 -m pytest -m "not real" tests/test_providers.py tests/test_reaggregate.py tests/test_evaluate_report.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full credential-free test suite**

Run:

```bash
python3 -m pytest -m "not real"
```

Expected: PASS. If a test requires a provider unexpectedly, fix the marker or test setup before committing.

- [ ] **Step 3: Inspect changed files**

Run:

```bash
git status --short
git diff -- README.md REPORT.md rfp_rag/contracts.py tests/test_evaluate_report.py tests/test_providers.py
```

Expected: only intended source/docs changes appear. `uv.lock` may still appear untracked; do not stage it.

- [ ] **Step 4: Confirm open lane contract semantics**

Run:

```bash
python3 - <<'PY'
from rfp_rag.contracts import open_contract

contract = open_contract()
semantics = contract["quality_semantics"]["open"]
assert semantics["claims_semantic_quality"] is False
assert semantics["forbidden_completion_claim"] == "rag_quality_complete"
print(contract["contract_version"])
print(contract["required_commands"])
PY
```

Expected:

```text
rfp-rag-open-v1
```

The printed commands should match the README command, including `--min-score` only if calibrated.

- [ ] **Step 5: Commit intended changes**

If artifacts are intentionally tracked in this repository, include `artifacts/eval_open` and relevant open artifacts. If artifacts are not tracked, commit only docs/source/test changes.

Run:

```bash
git add README.md REPORT.md rfp_rag/contracts.py tests/test_evaluate_report.py tests/test_providers.py
git status --short
git commit -m "docs: close open lane evidence"
```

If some listed files were not modified, `git add` will ignore them. Before committing, confirm `uv.lock` is not staged.

## Self-Review

- Spec coverage: The plan covers evidence production, score calibration, README/REPORT interpretation, missing prerequisite handling, credential-free tests, and avoiding `uv.lock`.
- Placeholder scan: The only variable value is `OPEN_MIN_SCORE`, computed by a concrete command from `artifacts/eval_open/metrics.json`. Documentation examples require replacing metrics with exact values produced during execution.
- Type consistency: The plan uses existing lane names and files: `open`, `rfp-rag-open-v1`, `artifacts/index_open`, `artifacts/eval_open`, `OPEN_REQUIRED_COMMANDS`, and `rag_quality_complete`.
