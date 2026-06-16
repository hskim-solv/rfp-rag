# ADR-0009: OCR/VLM 전 로컬 visual candidate baseline 채택

- 상태: 채택
- 날짜: 2026-06-16
- 결정자: Codex 추천 -> 사용자 "그래 너 추천대로 가자" 승인

## 배경

ADR-0007로 타깃 visual-structure extraction lane을 채택했고, 이후 reviewer gold
set과 candidate-vs-gold evaluator가 생겼다. 다음 선택지는 바로 OCR/VLM 후보를
도입할지, deterministic no-model 기준선을 먼저 둘지다.

비교 기준선 없이 OCR/VLM을 붙이면 비용과 복잡도는 늘지만, 실제로 무엇을 개선했는지
분리해서 주장하기 어렵다. 따라서 기존 `artifacts/visual_structure/records.jsonl`만
사용해 credential-free 후보 fact를 만들고, 같은 evaluator로 점수를 산출하는 baseline
lane이 필요하다.

## 선택 기준

| 기준 | 가중치 | 근거 |
|------|--------|------|
| 비교 가능성 | 높음 | OCR/VLM 후보가 단순 queue prior보다 나은지 보여야 함 |
| offline/credential-free 유지 | 높음 | visual baseline은 API key 없이 재현되어야 함 |
| gold set 검증력 노출 | 높음 | rejected label이 false claim을 잡는지 확인해야 함 |
| 구현 범위 | 중 | 다음 OCR/VLM 선택 전에 빠르게 floor metric을 고정해야 함 |
| 최종 품질 기여 | 중 | baseline 자체보다 이후 후보의 개선 폭을 설명하는 역할 |

## 후보 비교

검증일: 2026-06-16. 후보 비교는 저장소 내부 artifacts와 reviewer gold set 기준이다.
특정 OCR/VLM provider나 모델은 아직 선택하지 않는다.

| 기준 | 후보 A: 바로 OCR/VLM 후보 도입 | 후보 B: deterministic no-model baseline 선행 | 후보 C: reviewer gold만 유지 |
|------|------|------|------|
| 비교 가능성 | 모델 산출물 단독 점수만 생김. 개선 폭 설명이 약함 | queue prior 대비 precision/recall/F1 개선 폭을 설명 가능 | gold 완성도는 보이지만 extractor 비교군 없음 |
| offline/credential-free | provider에 따라 비용/credential 필요 | 완전 credential-free | credential-free |
| gold 검증력 노출 | 가능하지만 비용이 듦 | negative violation과 unknown claim을 즉시 계측 | candidate가 없어 precision 검증이 미사용 |
| 구현 범위 | parser/render/OCR/model/schema 선택까지 넓어짐 | records -> candidate facts 변환과 기존 evaluator 재사용 | 추가 구현 없음 |
| 최종 품질 기여 | 실제 품질 후보가 될 수 있음 | 품질 floor와 실패 유형을 고정 | 이후 후보 성능 해석이 빈약 |

## 결정

**후보 B: deterministic no-model visual baseline을 OCR/VLM 채택 전에 선행한다.**

이 lane은 `reviewed_needs_extraction` visual records를 하나의 candidate fact로
변환하고, visual type별 우선 field를 선택한다. 산출물은
`artifacts/visual_local_baseline/candidate_facts.jsonl`과 `summary.json`이며,
기존 `run_visual_gold_eval`로 평가한다.

초기 실행 결과:

| metric | value |
|---|---:|
| candidate_fact_count | `60` |
| positive_gold_count | `11` |
| negative_gold_count | `49` |
| precision | `0.15` |
| recall | `0.81818182` |
| f1 | `0.25352113` |
| false_positive_count | `51` |
| false_negative_count | `2` |
| negative_violation_count | `32` |
| unknown_candidate_count | `19` |

해석: 이 기준선은 recall은 높지만 precision이 낮다. 즉 이후 OCR/VLM 또는
OCR+layout 후보는 최소한 recall을 유지하면서 negative violation과 unknown claim을
크게 줄여야 "비자명한 개선"이라고 주장할 수 있다.

후속 실행 결과: 2026-06-16에 `needs_page_review` 50 records를 추가로 page-review해
gold set을 110 records로 확장했다. 같은 baseline을
`--review-status reviewed_needs_extraction --review-status needs_page_review`로 다시
실행한 결과는 다음과 같다.

| metric | value |
|---|---:|
| candidate_fact_count | `110` |
| positive_gold_count | `25` |
| negative_gold_count | `85` |
| precision | `0.17272727` |
| recall | `0.76` |
| f1 | `0.28148148` |
| false_positive_count | `91` |
| false_negative_count | `6` |
| negative_violation_count | `52` |
| unknown_candidate_count | `39` |

확장 결과에서도 기준선의 역할은 동일하다. Queue prior만 믿으면 recall은 어느 정도
나오지만 unsupported visual claim이 많다. 이후 candidate는 이 기준선 대비 F1과
negative violation을 개선해야 하며, recall이 낮아질 경우 그 trade-off를 명시해야 한다.

## 탈락 사유

- 후보 A: 바로 OCR/VLM을 붙이면 모델 품질과 queue prior 효과가 섞여 개선 폭을
  설명하기 어렵다. 또한 provider/model/schema 선택 ADR이 아직 없다.
- 후보 C: reviewer gold만으로는 positive/negative label의 존재는 확인되지만,
  candidate extractor의 실패 유형을 수치화하지 못한다.

## 재검토 조건

- OCR/VLM 후보가 local baseline 대비 recall을 유지하지 못하거나 precision 개선이
  미미할 때
- reviewer gold set이 확장되어 baseline field-prior 자체가 더 이상 비교군으로
  부적절해질 때
- deterministic layout/OCR 후보가 API 기반 VLM보다 충분한 precision 개선을 보일 때
- visual-risk eval subset에서 negative violation 목표를 별도 gate로 승격할 때

## 출처

- `artifacts/visual_structure/records.jsonl`
- `docs/evidence/visual-structure-review-facts.seed.jsonl`
- `artifacts/visual_local_baseline/summary.json`
- `artifacts/visual_local_baseline_eval/summary.json`
- `artifacts/visual_local_baseline_expanded/summary.json`
- `artifacts/visual_local_baseline_expanded_eval/summary.json`
- `REPORT.md` §13-10
