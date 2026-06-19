# ADR-0002: RAG 평가 judge 라이브러리 선정 (소급)

- 상태: 대체됨 (ADR-0021)
- 날짜: 2026-06-11 (구현 선행 — real lane 사이클에서 기 채택, 본 ADR로 비교를 소급 기록)
- 결정자: Claude 제안 → 사용자 승인

## 배경

real lane 게이트 `rag_quality_complete`는 faithfulness ≥ 0.80, answer_relevancy ≥ 0.70을 요구한다
(`rfp_rag/evaluate.py`의 `RAGAS_THRESHOLDS`). LLM-as-judge 채점을 직접 구현할지, 검증된
라이브러리를 쓸지 결정이 필요했다. 평가는 자체 `evaluate.py` 파이프라인에 내장되므로
"함수로 호출 가능한 메트릭"이 필요하고, judge 모델은 `RFP_JUDGE_MODEL`로 교체 가능해야 한다.

## 선택 기준

| 기준 | 가중치 | 근거 |
|------|--------|------|
| RAG 특화 메트릭의 검증된 구현 | 높음 | faithfulness(문장 분해→근거 대조)는 직접 구현 시 그 구현 자체를 검증해야 하는 부담 |
| 파이프라인 내장 용이성 (함수형 API) | 높음 | 자체 evaluate.py 게이트에 내장 — 별도 테스트 러너/플랫폼 강제는 마이너스 |
| judge 모델 주입 자유도 | 높음 | `RFP_JUDGE_MODEL` 오버라이드로 비용 실험 (gpt-5.4 ↔ mini) |
| 외부 플랫폼 비종속 | 중 | 게이트 판정은 로컬 artifacts로 — 클라우드 업로드 전제 도구는 부적합 |
| 유지보수 전망 | 중 | 게이트의 심장이므로 중단 시 영향 큼 |

## 후보 비교 (2026-06-11 웹 검증)

| 기준 | ragas | deepeval | TruLens | 자체 구현 |
|------|-------|----------|---------|----------|
| RAG 메트릭 (faithfulness/relevancy) | O (전용) | O (+Contextual P/R) | O (RAG triad) | 직접 작성·검증 필요 |
| API 형태 | 함수형 (`single_turn_ascore`) | pytest 러너 중심 (`deepeval test run`) | 앱 계측(instrumentation) 중심 | 자유 |
| judge 모델 주입 | LangChain 래퍼로 주입 | O | O | 자유 |
| 외부 플랫폼 | 없음 (로컬 완결) | Confident AI 연계 (선택사항, 로컬 동작 확인됨) | 로컬 동작 | 없음 |
| 라이선스 | Apache-2.0 | Apache-2.0 | MIT | - |
| GitHub stars (규모 감각) | 14.3k | 16.1k | 3.4k | - |
| 릴리스 활동 | v0.4.3 (2025-01) — **2026년 들어 릴리스 없음** | 매우 활발 (주 단위) | 활발 (월 단위, v2.8.1 2025-05) | - |

비고 (통념과 다른 검증 결과):
- 커뮤니티 규모·릴리스 빈도는 **deepeval이 ragas보다 활발**하다. "ragas가 사실상 표준"이라는
  통념은 2026년 기준 과장 — 채택 근거는 표준성이 아니라 API 형태 적합성이다.
- 현재 사용 중인 `LangchainLLMWrapper`는 ragas 최신에서 **deprecated** (`llm_factory()` 권장).
  동작은 유지되나 마이그레이션 부채로 기록한다.

## 결정

**ragas** — faithfulness/relevancy를 함수 한 줄로 자체 파이프라인(`judge.py`)에 내장할 수 있고,
LangChain 래퍼로 judge 모델을 env var 하나로 교체한다. 게이트 판정이 로컬 artifacts로 완결되어
외부 플랫폼 종속이 없다.

## 탈락 사유

- deepeval: 메트릭 품질은 대등하나 pytest 러너 중심 워크플로가 자체 게이트 파이프라인과 겹침
  (평가를 deepeval 테스트로 재구성해야 이점이 남). Confident AI 업셀 표면도 불필요.
- TruLens: 앱 전체 계측 중심이라 "저장된 predictions에 점수만 부여"하는 용도에 과함. 커뮤니티 규모 열위.
- 자체 구현: faithfulness의 문장 분해·근거 대조 로직을 재발명하고 그 구현을 다시 검증해야 함 — 부담 대비 이득 없음.

## 재검토 조건

- ragas가 `LangchainLLMWrapper`를 제거하는 메이저 업데이트 (현재 deprecated) → `llm_factory()` 마이그레이션
- ragas 릴리스 공백 장기화 (2026-01 이후 무릴리스 지속 시 deepeval 재평가)
- 게이트 메트릭 확장 필요 시 (예: contextual precision/recall — deepeval이 더 풍부)

## 출처

- https://github.com/explodinggradients/ragas (메트릭 소스, LICENSE, releases)
- https://pypi.org/project/ragas/
- https://github.com/confident-ai/deepeval (README — 메트릭, pytest 통합, Confident AI)
- https://github.com/truera/trulens (releases, LICENSE)
