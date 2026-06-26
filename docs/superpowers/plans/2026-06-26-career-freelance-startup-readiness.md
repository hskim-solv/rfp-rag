# Career Freelance Startup Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current public-safe hosted Agentic RAG portfolio into a measurable package for three different outcomes: senior AI Agent/RAG employment, paid freelance work, and startup discovery.

**Architecture:** Add one lightweight business-readiness scorecard that reads existing repo evidence and fails closed when claims are not backed by files. Then add three audience-specific documents: hiring case pack, freelance offer pack, and startup validation pack. Keep the technical claim honest: this is a strong hosted reviewer demo and production-adjacent AI system, not a full SaaS business yet.

**Tech Stack:** Python 3.11+, standard library JSON/pathlib, pytest, existing `rfp_rag` artifact style, Markdown portfolio docs.

---

## Scope And Non-Goals

This plan does not add a new vector DB, cloud provider, payment system, auth vendor, CRM, or analytics product. Those would require ADR comparison before adoption.

This plan does not claim full hosted SaaS production readiness. It creates evidence that the repo is:

- strong enough to lead senior AI Agent/RAG job applications;
- packageable enough to sell small or medium document-AI freelance projects;
- structured enough to begin startup customer discovery without pretending product-market fit exists.

## File Structure

- Create: `rfp_rag/business_readiness.py`
  - Responsibility: compute employment, freelance, and startup readiness scores from existing docs/artifacts.
  - Interface: `python -m rfp_rag.business_readiness --out artifacts/business_readiness/summary.json`.
- Create: `tests/test_business_readiness.py`
  - Responsibility: verify fail-closed behavior, thresholds, and non-claim handling.
- Modify: `rfp_rag/portfolio_check.py`
  - Responsibility: include the business readiness artifact as a required portfolio evidence item.
- Modify: `tests/test_portfolio_check.py`
  - Responsibility: verify `portfolio_check` expects the new artifact.
- Create: `docs/portfolio/business-readiness-scorecard.md`
  - Responsibility: human-readable interpretation of the machine artifact.
- Create: `docs/portfolio/freelance-offer-pack.md`
  - Responsibility: concrete external-facing packages, scope boundaries, pricing bands, delivery proof.
- Create: `docs/portfolio/startup-validation-plan.md`
  - Responsibility: startup hypothesis, target customers, interview script, non-claims, validation gates.
- Modify: `docs/portfolio/company-fit-matrix.md`
  - Responsibility: add a short section mapping the project to employment, freelance, and startup buyer lenses.
- Modify: `docs/portfolio/claim-manifest.json`
  - Responsibility: add `business_readiness_scorecard` as a proven claim only after the artifact exists.
- Modify: `README.md`
  - Responsibility: add a short “Career / Freelance / Startup Readiness” section linking to the new docs and command.

## Acceptance Criteria

- `uv run python -m rfp_rag.business_readiness --out artifacts/business_readiness/summary.json` exits 0.
- `artifacts/business_readiness/summary.json` records:
  - `employment_ready: true` when score is at least 90.
  - `freelance_ready: true` when score is at least 80.
  - `startup_discovery_ready: true` when score is at least 65.
  - `startup_saas_ready: false` until production SaaS evidence exists.
- `uv run pytest tests/test_business_readiness.py tests/test_portfolio_check.py -q` passes.
- `uv run python -m rfp_rag.portfolio_check --out artifacts/portfolio_check/summary.json` passes.
- `uv run python -m rfp_rag.final_portfolio_scorecard` still passes.
- `uv run pytest -m "not real" -q` passes.

## Task 1: Business Readiness Scorecard

**Files:**
- Create: `rfp_rag/business_readiness.py`
- Create: `tests/test_business_readiness.py`

- [ ] **Step 1: Write failing tests for complete evidence**

Create `tests/test_business_readiness.py` with this content:

```python
from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.business_readiness import evaluate_business_readiness


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def seed_complete_repo(root: Path) -> None:
    write_json(
        root / "artifacts/final_portfolio_scorecard/summary.json",
        {
            "final_portfolio_scorecard_complete": True,
            "failed": [],
            "score_total": 100,
        },
    )
    write_json(
        root / "artifacts/hosted_demo_smoke/summary.json",
        {
            "hosted_demo_smoke_complete": True,
            "failed": [],
            "observed_git_sha": "abc1234",
            "metrics": {"rate_limit_boundary_pass": 1.0},
        },
    )
    write_json(
        root / "artifacts/fresh_clone_smoke/summary.json",
        {"fresh_clone_offline_smoke_complete": True, "failed": []},
    )
    write_json(
        root / "artifacts/production_readiness/summary.json",
        {"production_facing_readiness_complete": True, "failed": []},
    )
    write_json(
        root / "artifacts/stage4_ops_risk_scorecard/summary.json",
        {"failed": [], "metrics": {"redaction_scan_pass": 1.0}},
    )
    write_text(root / "docs/portfolio/case-study.md", "source-first Agentic RAG case study")
    write_text(root / "docs/portfolio/company-fit-matrix.md", "Senior AI Agent Engineer")
    write_text(root / "docs/portfolio/senior-reviewer-pack.md", "10-minute reviewer path")
    write_text(root / "docs/portfolio/freelance-offer-pack.md", "fixed-scope package")
    write_text(root / "docs/portfolio/startup-validation-plan.md", "customer interview gate")


def test_evaluate_business_readiness_scores_complete_repo(tmp_path: Path) -> None:
    seed_complete_repo(tmp_path)

    summary = evaluate_business_readiness(root=tmp_path)

    assert summary["business_readiness_complete"] is True
    assert summary["employment_ready"] is True
    assert summary["freelance_ready"] is True
    assert summary["startup_discovery_ready"] is True
    assert summary["startup_saas_ready"] is False
    assert summary["scores"]["employment"] >= 90
    assert summary["scores"]["freelance"] >= 80
    assert summary["scores"]["startup_discovery"] >= 65
    assert "full_saas_production" in summary["non_claims"]
    assert summary["failed"] == []


def test_evaluate_business_readiness_fails_closed_without_freelance_pack(
    tmp_path: Path,
) -> None:
    seed_complete_repo(tmp_path)
    (tmp_path / "docs/portfolio/freelance-offer-pack.md").unlink()

    summary = evaluate_business_readiness(root=tmp_path)

    assert summary["business_readiness_complete"] is False
    assert summary["freelance_ready"] is False
    assert "freelance_offer_pack_present" in summary["failed"]
    assert summary["scores"]["freelance"] < 80


def test_evaluate_business_readiness_does_not_claim_saas_without_saas_evidence(
    tmp_path: Path,
) -> None:
    seed_complete_repo(tmp_path)

    summary = evaluate_business_readiness(root=tmp_path)

    assert summary["startup_saas_ready"] is False
    assert summary["evidence"]["startup"]["saas_production_evidence"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_business_readiness.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'rfp_rag.business_readiness'`.

- [ ] **Step 3: Implement scorecard**

Create `rfp_rag/business_readiness.py` with this content:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_OUT = Path("artifacts/business_readiness/summary.json")

REQUIRED_DOCS = {
    "case_study": Path("docs/portfolio/case-study.md"),
    "company_fit_matrix": Path("docs/portfolio/company-fit-matrix.md"),
    "senior_reviewer_pack": Path("docs/portfolio/senior-reviewer-pack.md"),
    "freelance_offer_pack": Path("docs/portfolio/freelance-offer-pack.md"),
    "startup_validation_plan": Path("docs/portfolio/startup-validation-plan.md"),
}

REQUIRED_ARTIFACTS = {
    "final_portfolio_scorecard": Path("artifacts/final_portfolio_scorecard/summary.json"),
    "hosted_demo_smoke": Path("artifacts/hosted_demo_smoke/summary.json"),
    "fresh_clone_smoke": Path("artifacts/fresh_clone_smoke/summary.json"),
    "production_readiness": Path("artifacts/production_readiness/summary.json"),
    "stage4_ops_risk_scorecard": Path("artifacts/stage4_ops_risk_scorecard/summary.json"),
}

THRESHOLDS = {
    "employment": 90,
    "freelance": 80,
    "startup_discovery": 65,
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _complete(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is True and payload.get("failed", []) == []


def _doc_present(root: Path, key: str) -> bool:
    path = root / REQUIRED_DOCS[key]
    return path.is_file() and len(path.read_text(encoding="utf-8").strip()) >= 40


def evaluate_business_readiness(*, root: Path = Path(".")) -> dict[str, Any]:
    root = root.resolve()
    artifacts = {
        key: _read_json(root / path) for key, path in REQUIRED_ARTIFACTS.items()
    }
    docs = {key: _doc_present(root, key) for key in REQUIRED_DOCS}

    final_score = artifacts["final_portfolio_scorecard"].get("score_total", 0)
    hosted_ok = _complete(artifacts["hosted_demo_smoke"], "hosted_demo_smoke_complete")
    fresh_clone_ok = _complete(
        artifacts["fresh_clone_smoke"], "fresh_clone_offline_smoke_complete"
    )
    production_ok = _complete(
        artifacts["production_readiness"], "production_facing_readiness_complete"
    )
    ops_risk_ok = artifacts["stage4_ops_risk_scorecard"].get("failed", []) == []

    employment_score = 0
    employment_score += 30 if final_score >= 90 else 0
    employment_score += 20 if hosted_ok else 0
    employment_score += 15 if fresh_clone_ok else 0
    employment_score += 15 if production_ok else 0
    employment_score += 10 if docs["case_study"] else 0
    employment_score += 10 if docs["company_fit_matrix"] else 0

    freelance_score = 0
    freelance_score += 25 if hosted_ok else 0
    freelance_score += 20 if production_ok else 0
    freelance_score += 15 if ops_risk_ok else 0
    freelance_score += 15 if docs["freelance_offer_pack"] else 0
    freelance_score += 15 if docs["senior_reviewer_pack"] else 0
    freelance_score += 10 if fresh_clone_ok else 0

    startup_discovery_score = 0
    startup_discovery_score += 20 if docs["startup_validation_plan"] else 0
    startup_discovery_score += 15 if docs["case_study"] else 0
    startup_discovery_score += 15 if docs["freelance_offer_pack"] else 0
    startup_discovery_score += 15 if hosted_ok else 0
    startup_discovery_score += 10 if production_ok else 0
    startup_discovery_score += 10 if ops_risk_ok else 0
    startup_discovery_score += 15 if docs["company_fit_matrix"] else 0

    checks = {
        "case_study_present": docs["case_study"],
        "company_fit_matrix_present": docs["company_fit_matrix"],
        "senior_reviewer_pack_present": docs["senior_reviewer_pack"],
        "freelance_offer_pack_present": docs["freelance_offer_pack"],
        "startup_validation_plan_present": docs["startup_validation_plan"],
        "final_portfolio_score_at_least_90": final_score >= 90,
        "hosted_demo_smoke_pass": hosted_ok,
        "fresh_clone_smoke_pass": fresh_clone_ok,
        "production_readiness_pass": production_ok,
        "ops_risk_scorecard_pass": ops_risk_ok,
    }
    scores = {
        "employment": employment_score,
        "freelance": freelance_score,
        "startup_discovery": startup_discovery_score,
    }
    failed = [key for key, value in checks.items() if not value]
    failed.extend(
        f"{key}_score_below_{threshold}"
        for key, threshold in THRESHOLDS.items()
        if scores[key] < threshold
    )
    failed = sorted(set(failed))

    return {
        "schema_version": "business-readiness-v1",
        "business_readiness_complete": not failed,
        "scores": scores,
        "thresholds": THRESHOLDS,
        "employment_ready": scores["employment"] >= THRESHOLDS["employment"],
        "freelance_ready": scores["freelance"] >= THRESHOLDS["freelance"],
        "startup_discovery_ready": (
            scores["startup_discovery"] >= THRESHOLDS["startup_discovery"]
        ),
        "startup_saas_ready": False,
        "checks": checks,
        "evidence": {
            "employment": {
                "portfolio_score": final_score,
                "hosted_demo_smoke": hosted_ok,
                "fresh_clone_smoke": fresh_clone_ok,
                "case_study": docs["case_study"],
                "company_fit_matrix": docs["company_fit_matrix"],
            },
            "freelance": {
                "hosted_demo_smoke": hosted_ok,
                "production_readiness": production_ok,
                "ops_risk_scorecard": ops_risk_ok,
                "offer_pack": docs["freelance_offer_pack"],
                "reviewer_pack": docs["senior_reviewer_pack"],
            },
            "startup": {
                "validation_plan": docs["startup_validation_plan"],
                "case_study": docs["case_study"],
                "offer_pack": docs["freelance_offer_pack"],
                "saas_production_evidence": False,
            },
        },
        "failed": failed,
        "non_claims": [
            "full_saas_production",
            "product_market_fit",
            "live_customer_revenue",
            "multi_tenant_security_review",
            "paid_cloud_slo",
        ],
    }


def write_business_readiness(
    *, root: Path = Path("."), out: Path = DEFAULT_OUT
) -> dict[str, Any]:
    summary = evaluate_business_readiness(root=root)
    target = root / out if not out.is_absolute() else out
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    summary = write_business_readiness(root=args.root, out=args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["business_readiness_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_business_readiness.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add rfp_rag/business_readiness.py tests/test_business_readiness.py
git commit -m "feat: add business readiness scorecard"
```

## Task 2: Human Business Readiness Scorecard Document

**Files:**
- Create: `docs/portfolio/business-readiness-scorecard.md`

- [ ] **Step 1: Create scorecard document**

Create `docs/portfolio/business-readiness-scorecard.md` with this content:

```markdown
# Business Readiness Scorecard

This document separates three different questions that are easy to mix up:

1. Can this project help win senior AI Agent/RAG interviews?
2. Can this project support paid freelance proposals?
3. Can this project become a startup product?

## Current Answer

| Outcome | Status | Reason |
| --- | --- | --- |
| Senior AI Agent/RAG employment | Ready to lead with | The repo has source-first RAG, LangGraph agent workflow, FastAPI service, Docker/CI, hosted reviewer demo evidence, scorecards, guardrails, and fresh clone smoke. |
| Freelance RAG/document-AI work | Ready for scoped discovery and small/medium projects | The repo proves delivery ability, but needs each client scope constrained by data access, deployment target, support window, and acceptance tests. |
| Startup SaaS | Ready for customer discovery, not full SaaS sales | The repo proves technical feasibility, but not recurring user demand, onboarding UX, multi-tenant operations, billing, support, or live SLOs. |

## Machine Check

Run:

```bash
uv run python -m rfp_rag.business_readiness --out artifacts/business_readiness/summary.json
```

Expected readiness thresholds:

| Score | Threshold | Meaning |
| --- | ---: | --- |
| employment | 90 | Strong enough to lead senior AI Agent/RAG applications. |
| freelance | 80 | Strong enough to use in paid project discovery and proposals. |
| startup_discovery | 65 | Strong enough to interview customers and test willingness to pay. |

## Non-Claims

- This is not yet full hosted SaaS.
- This does not prove product-market fit.
- This does not prove live customer revenue.
- This does not prove multi-tenant security review.
- This does not prove paid cloud SLO.

## Evidence Map

| Claim | Evidence |
| --- | --- |
| Strong senior hiring signal | `docs/portfolio/case-study.md`, `docs/portfolio/company-fit-matrix.md`, `artifacts/final_portfolio_scorecard/summary.json` |
| Reviewer can inspect a public-safe demo | `artifacts/hosted_demo_smoke/summary.json`, `docs/portfolio/senior-reviewer-pack.md` |
| Client delivery process can be scoped | `docs/portfolio/freelance-offer-pack.md`, `docs/portfolio/demo-runbook.md` |
| Startup discovery can begin honestly | `docs/portfolio/startup-validation-plan.md` |
```

- [ ] **Step 2: Verify document exists**

Run:

```bash
test -s docs/portfolio/business-readiness-scorecard.md
```

Expected: exit code 0.

- [ ] **Step 3: Commit**

Run:

```bash
git add docs/portfolio/business-readiness-scorecard.md
git commit -m "docs: add business readiness scorecard"
```

## Task 3: Freelance Offer Pack

**Files:**
- Create: `docs/portfolio/freelance-offer-pack.md`

- [ ] **Step 1: Create freelance pack**

Create `docs/portfolio/freelance-offer-pack.md` with this content:

```markdown
# Freelance Offer Pack

This pack translates the RFP Agentic RAG system into paid project shapes. It is written for clients who need document search, question answering, or workflow automation over private business documents.

## Best-Fit Client Problems

- Internal document QA over PDFs, HWP, policies, manuals, contracts, proposals, or RFPs.
- Procurement or proposal teams that repeatedly inspect long public notices.
- Teams that need cited answers and abstention rather than generic chatbot replies.
- Teams that need a deployable backend, not a notebook.

## Offer 1: Document RAG Diagnostic

**Delivery window:** 1-2 weeks.

**Client inputs:**

- 20-50 representative documents.
- 20-40 real questions.
- One owner who can label answer usefulness.

**Deliverables:**

- Ingestion and parsing quality report.
- Retrieval baseline with recall and citation checks.
- Failure taxonomy.
- Recommendation: continue, redesign corpus, or stop.

**Acceptance tests:**

```bash
uv run python -m rfp_rag.business_readiness --out artifacts/business_readiness/summary.json
uv run python -m rfp_rag.portfolio_check --out artifacts/portfolio_check/summary.json
```

The client version should replace public RFP data with client-approved data and keep raw client content out of public artifacts.

## Offer 2: Internal RAG MVP

**Delivery window:** 3-6 weeks.

**Client inputs:**

- 100-1,000 documents.
- Access policy for who can query which documents.
- Deployment target: local server, cloud VM, or managed container.

**Deliverables:**

- FastAPI backend.
- Document ingestion job.
- Retrieval and answer endpoint.
- Citation-bearing answers.
- Basic auth boundary.
- Smoke tests and runbook.

**Acceptance tests:**

- `/healthz` returns 200.
- Answer endpoint returns citations for answerable questions.
- Unsupported questions abstain.
- Prompt injection fixtures do not override system rules.
- Fresh clone or clean deploy smoke passes.

## Offer 3: Agentic Workflow Automation

**Delivery window:** 6-10 weeks.

**Client inputs:**

- A repeated workflow with clear steps and owner approvals.
- Tool/API access boundaries.
- A list of actions requiring human approval.

**Deliverables:**

- LangGraph workflow with typed state.
- Tool allowlist.
- Checkpoint and replay path.
- Human approval node.
- Failure analysis report.

**Acceptance tests:**

- Tool budget is enforced.
- Human approval is required for write/export actions.
- Failed runs are traceable.
- Retry/rewrite behavior is visible in logs or artifacts.

## Pricing Guidance

These are positioning bands, not quotes:

| Package | Suggested band | Why |
| --- | ---: | --- |
| Document RAG Diagnostic | KRW 3M-8M | Bounded analysis with clear stop/go output. |
| Internal RAG MVP | KRW 12M-35M | Backend, ingestion, evaluation, deployment, and runbook. |
| Agentic Workflow Automation | KRW 30M-80M | Workflow design, tool contracts, HITL, evaluation, and operational hardening. |

## Scope Boundaries

- No unbounded data cleanup.
- No unsupported cloud bill responsibility.
- No customer production secret stored in this public repo.
- No model training, RLHF, or fine-tuning unless separately scoped.
- No legal, medical, or financial advice claims from generated answers.

## Proof From This Repo

- `docs/portfolio/case-study.md`
- `docs/portfolio/senior-reviewer-pack.md`
- `artifacts/hosted_demo_smoke/summary.json`
- `artifacts/final_portfolio_scorecard/summary.json`
- `scripts/reviewer-10m.sh`
```

- [ ] **Step 2: Verify document contains all three offers**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
text = Path("docs/portfolio/freelance-offer-pack.md").read_text()
for phrase in ["Document RAG Diagnostic", "Internal RAG MVP", "Agentic Workflow Automation"]:
    assert phrase in text
print("freelance_offer_pack_ok=true")
PY
```

Expected: `freelance_offer_pack_ok=true`.

- [ ] **Step 3: Commit**

Run:

```bash
git add docs/portfolio/freelance-offer-pack.md
git commit -m "docs: add freelance offer pack"
```

## Task 4: Startup Validation Plan

**Files:**
- Create: `docs/portfolio/startup-validation-plan.md`

- [ ] **Step 1: Create startup validation plan**

Create `docs/portfolio/startup-validation-plan.md` with this content:

```markdown
# Startup Validation Plan

This project can become a startup only if a narrow customer segment repeatedly pays for a painful document workflow. The current repo proves technical feasibility, not product-market fit.

## Initial Wedge

Target workflow:

> Korean procurement and proposal teams reviewing public RFPs need a cited, auditable assistant that finds requirements, risks, eligibility constraints, deadlines, and missing evidence faster than manual review.

## Hypotheses

| Hypothesis | Validation signal | Failure signal |
| --- | --- | --- |
| RFP review is frequent enough | Team reviews at least 10 RFPs per month. | Team reviews fewer than 3 RFPs per month. |
| Manual review pain is expensive | Team spends at least 2 person-days per important RFP. | Review is already cheap or outsourced casually. |
| Citation trust matters | Buyer rejects uncited chatbot answers. | Buyer accepts generic summaries without evidence. |
| Workflow integration matters | Buyer wants export, checklist, approval, or audit trail. | Buyer only wants one-off summarization. |
| Willingness to pay exists | Buyer accepts paid pilot or budget owner intro. | Buyer asks only for free trial without budget path. |

## Interview Script

Ask these in order:

1. How many RFPs or public notices did your team review last month?
2. Which step takes the most time?
3. What mistake would be costly if missed?
4. What source evidence must an answer show before you trust it?
5. Who signs off on bid/no-bid or proposal direction?
6. What system do you use after reviewing the RFP?
7. What would a useful export look like?
8. What would make this unusable in your environment?
9. What is the budget owner for this workflow?
10. Would you pay for a 2-week pilot if it reduced review time by 30%?

## Pilot Gate

Proceed to a paid pilot only if at least 3 of 5 interviewed teams meet all conditions:

- At least 10 reviewed RFPs per month.
- At least 2 person-days spent per important RFP.
- Requires cited evidence.
- Has a budget owner.
- Agrees to a paid pilot or a budget-owner meeting.

## MVP Scope

The MVP should include:

- document upload or controlled corpus import;
- cited answer endpoint;
- checklist extraction for eligibility, deadline, submission docs, budget, and evaluation criteria;
- reviewer approval/export flow;
- run-level audit evidence;
- workspace-level data deletion.

The MVP should not include:

- marketplace features;
- automatic bid submission;
- legal advice claims;
- broad cross-industry document automation;
- custom model training.

## Startup Readiness Boundary

Current status:

- Technical feasibility: strong.
- Hiring portfolio: strong.
- Freelance packaging: possible after offer pack.
- Startup discovery: ready after interviews begin.
- Full SaaS readiness: not yet.

The next irreversible decision is not a cloud architecture decision. It is whether procurement/proposal teams show repeated willingness to pay.
```

- [ ] **Step 2: Verify plan contains pilot gate**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
text = Path("docs/portfolio/startup-validation-plan.md").read_text()
assert "Pilot Gate" in text
assert "paid pilot" in text
assert "Full SaaS readiness: not yet." in text
print("startup_validation_plan_ok=true")
PY
```

Expected: `startup_validation_plan_ok=true`.

- [ ] **Step 3: Commit**

Run:

```bash
git add docs/portfolio/startup-validation-plan.md
git commit -m "docs: add startup validation plan"
```

## Task 5: Portfolio Check Integration

**Files:**
- Modify: `rfp_rag/portfolio_check.py`
- Modify: `tests/test_portfolio_check.py`
- Modify: `docs/portfolio/claim-manifest.json`

- [ ] **Step 1: Inspect existing portfolio check item pattern**

Run:

```bash
rg -n "fresh_clone_offline_smoke|required_artifacts|Criterion|portfolio" rfp_rag/portfolio_check.py tests/test_portfolio_check.py
```

Expected: output shows the current evidence item list and test fixture style.

- [ ] **Step 2: Write failing portfolio check test**

In `tests/test_portfolio_check.py`, add this assertion to the happy-path fixture test that already seeds required artifacts:

```python
assert "business_readiness" in summary["evidence"]
assert summary["metrics"]["business_readiness_pass"] == 1.0
```

Also add this fixture entry to the seeded artifact map:

```python
"artifacts/business_readiness/summary.json": {
    "business_readiness_complete": True,
    "employment_ready": True,
    "freelance_ready": True,
    "startup_discovery_ready": True,
    "startup_saas_ready": False,
    "failed": [],
}
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_portfolio_check.py -q
```

Expected: fail because `business_readiness` is not yet part of `portfolio_check`.

- [ ] **Step 4: Add business readiness item to portfolio check**

Modify `rfp_rag/portfolio_check.py` in the same item list that contains `fresh_clone_offline_smoke`:

```python
{
    "id": "business_readiness",
    "path": "artifacts/business_readiness/summary.json",
    "complete_field": "business_readiness_complete",
    "required": True,
}
```

Add this metric in the same style as other pass metrics:

```python
"business_readiness_pass": (
    1.0 if _complete(business_readiness, "business_readiness_complete") else 0.0
),
```

- [ ] **Step 5: Update claim manifest**

Modify `docs/portfolio/claim-manifest.json`:

Add to `proven_claims`:

```json
"business_readiness_scorecard"
```

Add to `required_machine_artifacts`:

```json
"artifacts/business_readiness/summary.json"
```

- [ ] **Step 6: Run tests**

Run:

```bash
uv run pytest tests/test_business_readiness.py tests/test_portfolio_check.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add rfp_rag/portfolio_check.py tests/test_portfolio_check.py docs/portfolio/claim-manifest.json
git commit -m "feat: require business readiness evidence"
```

## Task 6: README And Company Fit Update

**Files:**
- Modify: `README.md`
- Modify: `docs/portfolio/company-fit-matrix.md`

- [ ] **Step 1: Add README section**

Add this section near the portfolio/reviewer documentation links in `README.md`:

```markdown
## Career / Freelance / Startup Readiness

This repo is positioned for three different outcomes, with separate evidence boundaries:

- **Senior AI Agent/RAG employment:** ready to lead with when `final_portfolio_scorecard`, hosted demo smoke, fresh clone smoke, and portfolio check pass.
- **Freelance RAG/document-AI work:** ready for scoped discovery and bounded paid projects using `docs/portfolio/freelance-offer-pack.md`.
- **Startup SaaS:** ready for customer discovery using `docs/portfolio/startup-validation-plan.md`, but not claimed as full SaaS production.

Run:

```bash
uv run python -m rfp_rag.business_readiness --out artifacts/business_readiness/summary.json
```

Evidence:

- `docs/portfolio/business-readiness-scorecard.md`
- `docs/portfolio/freelance-offer-pack.md`
- `docs/portfolio/startup-validation-plan.md`
```

- [ ] **Step 2: Add company fit section**

Append this section to `docs/portfolio/company-fit-matrix.md`:

```markdown
## Outcome Lens

| Outcome | How to pitch this repo | Boundary |
| --- | --- | --- |
| Employment | Senior AI Agent/RAG system with source-first retrieval, LangGraph workflow, FastAPI service, CI, hosted reviewer evidence, and fail-closed scorecards. | Do not imply full SaaS operations or live SLOs. |
| Freelance | Proof that similar document-AI systems can be scoped, evaluated, deployed, and handed over with runbooks. | Do not accept unbounded data cleanup or undefined production support. |
| Startup | Technical base for procurement/RFP workflow discovery and paid-pilot interviews. | Do not claim product-market fit, revenue, or multi-tenant SaaS readiness. |
```

- [ ] **Step 3: Verify links and command mention**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
readme = Path("README.md").read_text()
matrix = Path("docs/portfolio/company-fit-matrix.md").read_text()
assert "Career / Freelance / Startup Readiness" in readme
assert "rfp_rag.business_readiness" in readme
assert "Outcome Lens" in matrix
print("readme_company_fit_update_ok=true")
PY
```

Expected: `readme_company_fit_update_ok=true`.

- [ ] **Step 4: Commit**

Run:

```bash
git add README.md docs/portfolio/company-fit-matrix.md
git commit -m "docs: explain career freelance startup readiness"
```

## Task 7: Generate Artifacts And Run Final Gates

**Files:**
- Generate: `artifacts/business_readiness/summary.json`
- Generate: `artifacts/portfolio_check/summary.json`
- Generate: `artifacts/final_portfolio_scorecard/summary.json`

- [ ] **Step 1: Generate business readiness artifact**

Run:

```bash
uv run python -m rfp_rag.business_readiness --out artifacts/business_readiness/summary.json
```

Expected key output:

```json
{
  "business_readiness_complete": true,
  "employment_ready": true,
  "freelance_ready": true,
  "startup_discovery_ready": true,
  "startup_saas_ready": false
}
```

- [ ] **Step 2: Run portfolio check**

Run:

```bash
uv run python -m rfp_rag.portfolio_check --out artifacts/portfolio_check/summary.json
```

Expected: command exits 0 and `failed` is `[]`.

- [ ] **Step 3: Run final scorecard**

Run:

```bash
uv run python -m rfp_rag.final_portfolio_scorecard
```

Expected: command exits 0 and `score_total` remains at least 100 if current scoring still caps at 100.

- [ ] **Step 4: Run targeted tests**

Run:

```bash
uv run pytest tests/test_business_readiness.py tests/test_portfolio_check.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Run full offline regression**

Run:

```bash
uv run pytest -m "not real" -q
```

Expected: all credential-free tests pass with real tests deselected.

- [ ] **Step 6: Commit**

Artifacts are local evidence and may be gitignored. Commit only source and docs changes:

```bash
git status --short
git add rfp_rag/business_readiness.py tests/test_business_readiness.py rfp_rag/portfolio_check.py tests/test_portfolio_check.py README.md docs/portfolio/business-readiness-scorecard.md docs/portfolio/freelance-offer-pack.md docs/portfolio/startup-validation-plan.md docs/portfolio/company-fit-matrix.md docs/portfolio/claim-manifest.json
git commit -m "feat: add career freelance startup readiness pack"
```

If earlier task commits were already made, this step should show no staged source/doc changes and no commit is needed.

## Task 8: PR And Reviewer Summary

**Files:**
- No required source modification.

- [ ] **Step 1: Push branch**

Run:

```bash
git push origin codex/production-complete-readiness
```

Expected: push succeeds.

- [ ] **Step 2: Check PR status**

Run:

```bash
gh pr checks 63 --watch --interval 10
```

Expected: credential-free regression and Docker smoke checks succeed.

- [ ] **Step 3: Prepare reviewer summary**

Use this summary in the PR comment or final report:

```markdown
Added a business readiness layer that separates employment, freelance, and startup claims.

- Employment: ready to lead senior AI Agent/RAG applications when existing portfolio gates pass.
- Freelance: ready for scoped paid discovery and document-AI projects with explicit scope boundaries.
- Startup: ready for customer discovery and paid-pilot validation, but still not claimed as full SaaS production.

Verification:
- `uv run python -m rfp_rag.business_readiness --out artifacts/business_readiness/summary.json`
- `uv run python -m rfp_rag.portfolio_check --out artifacts/portfolio_check/summary.json`
- `uv run python -m rfp_rag.final_portfolio_scorecard`
- `uv run pytest -m "not real" -q`
```

## Self-Review

Spec coverage:

- Employment readiness is covered by Task 1, Task 2, Task 5, Task 6, and Task 7.
- Freelance readiness is covered by Task 1, Task 3, Task 5, Task 6, and Task 7.
- Startup readiness is covered by Task 1, Task 4, Task 5, Task 6, and Task 7.
- Honest non-claims are covered by Task 1, Task 2, Task 4, and Task 6.

Placeholder scan:

- No task contains empty placeholder wording or open-ended “handle it somehow” instructions.
- Every code-producing task includes concrete file paths and concrete snippets.

Type consistency:

- The scorecard field is consistently named `business_readiness_complete`.
- The artifact path is consistently `artifacts/business_readiness/summary.json`.
- The module command is consistently `uv run python -m rfp_rag.business_readiness`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-26-career-freelance-startup-readiness.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.
