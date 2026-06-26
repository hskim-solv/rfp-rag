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
