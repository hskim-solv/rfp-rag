# Visual audit manual review - 2026-06-15

## Scope

This review covers the 15 documents selected by `artifacts/visual_audit/samples.jsonl`
after the visual parsing audit lane. Each selected document contributed up to 5
pages, for 75 rendered PDF pages total.

Review inputs:

- `artifacts/visual_audit/summary.json`
- `artifacts/visual_audit/samples.jsonl`
- `artifacts/visual_audit/review.md`
- rendered temporary sheets from `tmp/pdfs/visual_audit/sheets/`
- extracted page text lengths from `artifacts/parsed_docs/page_text/*.jsonl`

The temporary sheets are reproducible from the PDFs listed in
`samples.jsonl`; they are not canonical artifacts.

## Method

The selected PDF pages were rendered to PNG and reviewed in three independent
groups: ranks 1-5, 6-10, and 11-15. The review question was narrow: whether the
selected visual elements contain bid-review information not reliably recoverable
from extracted text alone.

All 75 selected pages had non-empty extracted text. This means the finding is not
"text extraction failed." The gap is visual structure: Gantt bar positions,
system architecture diagrams, organization hierarchies, target service models,
and dashboard screenshots.

## Aggregate result

| Review result | Count |
|---|---:|
| business-critical visual-only information: yes | 10 |
| business-critical visual-only information: uncertain | 1 |
| business-critical visual-only information: no | 4 |
| OCR/VLM recommendation: adopt now | 6 |
| OCR/VLM recommendation: inspect individual page | 5 |
| OCR/VLM recommendation: defer | 4 |

Affected fields:

| Field | Count |
|---|---:|
| schedule | 6 |
| requirements | 8 |
| system architecture | 5 |
| budget | 0 |
| evaluation | 0 |
| qualification | 0 |

## Per-document findings

| Rank | doc_id | Visual elements | Visual-only risk | Affected fields | Recommendation |
|---:|---|---|---|---|---|
| 1 | `doc:007` | scope tables, information-system scope table, education/vision diagram | no | none | defer |
| 2 | `doc:093` | overview tables, function tables, SW status table, redacted architecture placeholder | no | none | defer |
| 3 | `doc:034` | project organization chart, Gantt schedule, requirements summary/list tables | yes | schedule | adopt now |
| 4 | `doc:012` | notice box, budget/period table, target-data table, analysis dashboard screenshots | uncertain | requirements | inspect individual page |
| 5 | `doc:026` | goal hierarchy, map, Gantt schedule, project organization chart, output/activity table | yes | schedule, requirements | adopt now |
| 6 | `doc:071` | Gantt schedule, automatic analysis system concept diagram, train-set table, requirements table | yes | system architecture, requirements | inspect individual page |
| 7 | `doc:068` | project role table, Gantt schedule, target-system concept, AI/server architecture | yes | system architecture, requirements | adopt now |
| 8 | `doc:094` | linked-system table, target service model, incident flow | yes | system architecture, requirements | adopt now |
| 9 | `doc:060` | workflow, cost-sharing table, submission documents, spare-parts table, evaluation table | no | none | defer |
| 10 | `doc:002` | EIP architecture, H/W table, S/W table, application architecture, linked systems/SLA table | yes | system architecture, requirements | adopt now |
| 11 | `doc:040` | environment table, redacted configuration box, organization chart, Gantt schedule, requirements summary | yes | schedule | inspect individual page |
| 12 | `doc:069` | cover table, scope prose, large function table | no | none | defer |
| 13 | `doc:011` | business menu table, current/target system diagrams, environment table, organization chart, Gantt schedule | yes | system architecture, schedule, requirements | adopt now |
| 14 | `doc:047` | 28-month Gantt schedule, SW/infrastructure tables, requirements summary/list | yes | schedule, requirements | inspect individual page |
| 15 | `doc:037` | facility system table, organization chart, role table, Gantt schedule | yes | schedule | inspect individual page |

## Interpretation

The current `unhwp_text + libreoffice_pdf_visual evidence` strategy remains the
right baseline for searchable body text and page citation. It should not be
replaced by full-page OCR/VLM.

The audit does justify a targeted visual-structure extraction lane for the
following visual types:

- Gantt schedules
- organization charts
- system architecture and target service diagrams
- dashboard or UI screenshots that encode requirements

The next implementation should be page-level and evidence-preserving. It should
emit structured records linked to `doc_id`, `page`, visual type, extracted
business fields, and reviewer/verifier status. Provider or model selection is a
separate decision.
