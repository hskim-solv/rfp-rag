# ADR-0007: 타깃 visual-structure extraction lane 채택

- 상태: 채택
- 날짜: 2026-06-15
- 결정자: Codex 제안 -> 사용자 "진행해봐" 승인

## 배경

Source-first parsing lane은 RFP 100건의 HWP/PDF 원문을 검색(retrieval) 본문 source
of truth로 쓰고, CSV는 metadata registry로만 둔다. Parser quality와 visual audit
결과, 선택 페이지 75개 모두 텍스트는 추출됐지만 Gantt 일정, 조직도, 시스템 구성도,
목표 서비스 모델, dashboard screenshot처럼 위치/계층/흐름이 의미인 시각 구조는
텍스트 추출만으로 충분히 구조화되지 않는다.

따라서 OCR/VLM을 전면 도입할지, 현 전략을 유지할지, 타깃 visual-structure lane만
추가할지 결정이 필요하다.

## 선택 기준

| 기준 | 가중치 | 근거 |
|------|--------|------|
| source-first 본문 불변식 유지 | 높음 | RAG 본문은 원문 parsed artifacts, CSV는 metadata registry |
| visual-only 업무 필드 회수 | 높음 | 일정(schedule), 요구사항(requirements), 시스템 구성(system architecture) 누락 가능 |
| 비용/latency 통제 | 높음 | full-page VLM은 문서 수와 페이지 수에 따라 반복 비용이 커짐 |
| offline lane credential-free 유지 | 높음 | `pytest -m "not real"`과 offline gate는 API key 없이 통과해야 함 |
| trace/sensitive data 최소화 | 중 | raw page image와 model inputs는 persistent capture 대상에서 제외해야 함 |
| 평가 가능성 | 중 | 구조화 record와 page evidence로 회귀 평가해야 함 |

## 후보 비교

검증일: 2026-06-15. 후보 비교는 내부 artifacts와 수동 review evidence 기준이다.
특정 OCR/VLM provider나 모델은 아직 선택하지 않는다.

| 기준 | 현 전략 유지: `unhwp_text + libreoffice_pdf_visual evidence` | 전체 페이지 OCR/VLM | 타깃 page-level visual-structure extraction |
|------|------|------|------|
| source-first 본문 불변식 | 가장 안전. 본문 pipeline 변화 없음 | 위험. model output이 본문 source처럼 섞일 수 있음 | 안전. 본문은 유지하고 visual structure를 별도 record로 추가 |
| visual-only 업무 필드 회수 | 부족. 수동 review에서 yes 10건, uncertain 1건 | 높음. 단 필요 없는 페이지까지 처리 | 높음. Gantt/조직도/시스템 구성도/screenshot page만 처리 |
| 비용/latency | 최저 | 최고 | 중간. audit 후보 page만 처리 |
| offline credential-free | 유지 | real/API lane이 넓어짐 | 유지 가능. extraction artifact는 optional lane으로 분리 |
| trace/sensitive data | 안전 | raw image/model input 관리 부담 큼 | page-level redaction/retention policy 적용 가능 |
| 평가 가능성 | visual semantics 평가는 불가 | 출력 범위가 넓어 평가 설계가 어려움 | visual type별 schema와 review status로 평가 가능 |

## 결정

**타깃 page-level visual-structure extraction lane을 채택한다.**

이는 full OCR/VLM 전환이 아니다. 검색 본문 source of truth는 계속 parsed text이며,
visual lane은 page evidence에 연결된 보조 structured record를 만든다. 우선 대상은
manual review에서 반복 확인된 Gantt 일정, 조직도, 시스템 구성도/목표모델, dashboard
screenshot 요구사항이다.

초기 record는 최소한 다음 필드를 가져야 한다:

- `doc_id`
- `page`
- `visual_type`
- `business_fields`
- `structured_facts`
- `evidence_ref`
- `extractor`
- `confidence`
- `review_status`

Provider/model 선정은 별도 ADR에서 비교한다.

## 탈락 사유

- 현 전략 유지: 본문 검색(retrieval)과 citation에는 충분하지만, manual review에서
  visual-only 업무 정보가 10건 반복 발견되어 다음 품질 단계로는 부족하다.
- 전체 페이지 OCR/VLM: 범위가 과하고 비용/latency/trace 관리 부담이 크다. 또한 이미
  75개 선택 페이지 모두 non-empty text를 갖고 있어 "텍스트 rescue" 목적의 전면 OCR은
  근거가 약하다.

## 재검토 조건

- targeted lane 결과에서 유효 structured record 비율이 20% 미만일 때
- visual-only 필드가 budget/evaluation/qualification처럼 현재 대상 밖에서 반복 발견될 때
- provider 비용 또는 latency가 real lane 반복 평가 비용보다 커질 때
- deterministic layout parser가 Gantt/조직도/시스템 구성도를 충분히 회수할 수 있음이 검증될 때
- real/provider evaluation에서 visual records가 answer quality에 기여하지 않는 것으로 확인될 때

## 출처

- `artifacts/visual_audit/summary.json`
- `artifacts/visual_audit/samples.jsonl`
- `artifacts/visual_audit/review.md`
- `docs/evidence/visual-audit-manual-review-2026-06-15.md`
- `REPORT.md` §13-4
