# ADR-0012: Visual fact sidecar context 채택

- 상태: 채택
- 날짜: 2026-06-17
- 결정자: 사용자 "일단 B" 승인

## 배경

Visual gold/candidate lane은 110-record reviewer gold set과 candidate gate를 갖췄다.
현재 Tesseract OCR candidate는 `precision=0.76923077`, `recall=0.8`,
`f1=0.78431373`, `negative_violation_count=3`으로 visual-candidate gate를 통과한다.

다음 단계는 이 visual evidence를 RAG 답변 context에 연결하는 것이다. 단, 프로젝트의
source-first 불변식상 parsed RFP 본문 chunk와 OCR-derived visual facts를 같은 본문으로
섞으면 안 된다.

## 선택 기준

| 기준 | 가중치 | 근거 |
|---|---|---|
| source-first 경계 보존 | 높음 | parsed source text와 visual candidate evidence를 분리해야 함 |
| gate-passing evidence만 노출 | 높음 | candidate gate 실패 산출물이 answer context에 들어가면 안 됨 |
| retrieval 영향 최소화 | 높음 | visual lane은 아직 본문 retrieval ranking을 대체할 수준이 아님 |
| citation/audit 설명력 | 높음 | 답변에서 text evidence와 visual evidence가 구분되어야 함 |
| 구현 범위 | 중 | M3 closeout은 작고 검증 가능한 integration이어야 함 |

## 후보 비교

| 기준 | A: 본문 chunk에 직접 주입 | B: sidecar context 첨부 | C: visual 전용 vector index |
|---|---|---|---|
| source-first 경계 | 낮음. OCR fact가 본문처럼 섞임 | 높음. 별도 `visual_evidence`로 분리 | 중간. 별도 index지만 retrieval merge가 필요 |
| gate 적용 | 가능하나 chunk 생성 시점에 고정 | 높음. gate summary를 로딩 시 확인 | 가능하나 index lifecycle 복잡 |
| retrieval 영향 | 큼. 기존 score 분포 변경 | 없음. 기존 text retrieval 유지 | 큼. rank fusion 설계 필요 |
| citation/audit | 약함. 본문/visual 구분 어려움 | 높음. page-level visual source를 별도 표기 | 중간. 별도 citation schema 필요 |
| 구현 범위 | 작지만 위험 | 작고 안전 | 큼 |

## 결정

**B: visual facts를 sidecar로 유지하고, gate-passing candidate만 answer context에 분리 첨부한다.**

구현 원칙:

- `artifacts/visual_tesseract_candidate_expanded_gate/summary.json`의 `ok=true`를 확인한
  경우에만 candidate sidecar를 로드한다.
- retrieval ranking과 index chunk는 변경하지 않는다.
- retrieved `doc_id`에 해당하는 visual evidence를 result metadata의
  `visual_evidence`에 붙인다.
- LLM/judge context에는 `시각근거:` 라벨로 분리해 표시한다.
- `sources[]`에도 visual evidence를 노출해 UI/운영 로그에서 본문 근거와 구분할 수 있게 한다.

## 재검토 조건

- visual-only 질의가 text retrieval로는 관련 문서를 찾지 못하는 경우가 반복될 때
- visual facts가 page-level presence를 넘어 table item, schedule duration, role assignment
  등 semantic extraction으로 확장될 때
- visual evidence가 answer quality eval에서 무의미하거나 hallucination을 유발할 때
- visual-specific retrieval/reranking gate가 필요해질 때

## 출처

- `artifacts/visual_tesseract_candidate_expanded_eval/summary.json`
- `artifacts/visual_tesseract_candidate_expanded_gate/summary.json`
- `docs/adr/0011-local-tesseract-visual-candidate.md`
- `REPORT.md` §13-11
