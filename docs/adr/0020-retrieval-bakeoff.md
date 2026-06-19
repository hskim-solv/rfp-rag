# ADR-0020: Stage 2 retrieval bakeoff keeps vector and defers paid reranker

- 상태: 채택
- 날짜: 2026-06-18
- 결정자: Codex 제안, 기존 ADR-0008 및 현재 Stage 2 artifact 근거

## 배경

Stage 2 portfolio contract requires a retrieval bakeoff across the retrieval
modes that can be compared on the same frozen set without stale or mismatched
evidence. The repository now has fresh credential-free offline measurements for
vector, BM25, and hybrid RRF on the 545-query offline set. No same-set artifact
with `reranker="llm"` is present yet, and the older `artifacts/eval_open` run is
not accepted as reranker evidence.

ADR-0008 already decided that the reranker path is a lane-compatible LLM
reranker for `real_openai` or `open`, while offline `--reranker llm` remains
blocked to preserve the credential-free invariant. Therefore a full same-set
reranker bakeoff is a paid/API lane. It was attempted after approval, but the
`real_openai` path is currently blocked by OpenAI `insufficient_quota`, and the
`open` path produced a non-comparable 515-query set rather than the 545-query
bakeoff set.

## 선택 기준

| 기준 | 가중치 | 이유 |
|------|--------|------|
| Same frozen set | 높음 | bakeoff 비교는 query-set hash가 같아야만 채택/비채택 판단이 가능하다. |
| No-regression floors | 높음 | recall, citation validity, abstention, section hit, visual evidence, latency, cost가 모두 vector baseline 이상이어야 한다. |
| Credential-free invariant | 높음 | offline/no-real tests and local gates must not require API keys. |
| Honest portfolio claim | 높음 | senior portfolio evidence must not label stale or mismatched reranker results as comparable evidence. |
| Cost/quota control | 중 | reranker same-set execution uses `open` or `real_openai`; current OpenAI quota blocks the real path. |

## 후보 비교

검증일: 2026-06-18. Metrics are from local artifacts after regenerating
BM25/hybrid offline runs on the current 545-query set.

| 기준 | vector baseline | BM25 offline | hybrid RRF offline | LLM reranker open |
|------|------|------|------|------|
| Artifact | `artifacts/eval/metrics.json` | `artifacts/eval_bm25_offline/metrics.json` | `artifacts/eval_hybrid_offline/metrics.json` | not present on current same-set bakeoff |
| Query count | 545 | 545 | 545 | not measured |
| Same-set comparable | yes | yes | yes | no |
| `recall@5` | 0.9864 | 0.9835 | 0.9854 | not measured |
| `citation_validity` | 0.9845 | 1.0 | 1.0 | not measured |
| `abstention_pass` | 1.0 | 0.0667 | 0.0667 | not measured |
| `section_hit_rate` | 1.0 | 0.7667 | 0.6333 | not measured |
| `visual_evidence_hit_rate` | 0.92 | 1.0 | 1.0 | not measured |
| Cost/API | none | none | none | paid/API |
| Decision fitness | current baseline | not adopted due abstention/section regression | not adopted due abstention/section regression | not comparable until approved rerun |

## 결정

Keep `vector` as the active retrieval baseline. The current required bakeoff is
closed over `vector`, `bm25`, and `hybrid_rrf`, because those are the modes with
same-set comparable evidence. `reranker` remains optional/deferred, not a failed
required mode, until a same-set paid/API LLM reranker run exists and wins without
regressions.

This is a deliberate non-adoption decision for BM25 and hybrid RRF as gate
replacements, not a missing implementation. BM25 and hybrid are implemented and
measured, but both regress abstention and section hit behavior against vector.

## 탈락 사유

- BM25 offline: strong exact-match behavior, but `abstention_pass=0.0667` and
  `section_hit_rate=0.7667` regress below vector.
- hybrid RRF offline: improves some lexical/visual behavior, but
  `abstention_pass=0.0667` and `section_hit_rate=0.6333` regress below vector.
- LLM reranker open/real: no current same-set `reranker="llm"` artifact exists;
  the real path is blocked by `insufficient_quota`, and the open attempt used a
  non-comparable query set.

## 재검토 조건

- OpenAI quota is available or an accepted `open` provider run can reproduce the
  same 545-query set, and a same-set `open` or `real_openai` reranker evaluation
  is generated.
- A credential-free local reranker is proposed through a new ADR that compares
  local CrossEncoder or another deterministic model against the current
  lane-compatible LLM reranker decision.
- Hybrid/BM25 abstention and section regressions are fixed and remeasured on
  the same frozen set.

## 출처

- `artifacts/eval/metrics.json`
- `artifacts/eval_bm25_offline/metrics.json`
- `artifacts/eval_hybrid_offline/metrics.json`
- `artifacts/eval_open/metrics.json`
- `artifacts/retrieval_bakeoff/summary.json`
- `docs/adr/0008-lane-compatible-llm-reranker.md`
