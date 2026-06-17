# ADR-0014: FastAPI service surface

- 상태: 채택
- 날짜: 2026-06-17
- 결정자: 사용자 최종 목표(FastAPI/Pydantic async/SSE service) + Codex 비교 후 적용

## 배경

프로젝트의 최종 산출물은 source-first RAG 품질 artifact만이 아니라 운영 가능한
Agentic RAG system이다. 현재 CLI와 eval lane은 강하지만, 외부 소비자가 호출할 수
있는 typed API, streaming 응답, health/gate 노출 표면이 없다. 이번 slice는 기존
`answer_query`/artifact/gate 로직을 재사용하는 얇은 service layer를 추가한다.

## 선택 기준

- 높음: Python 3.11+ / Pydantic typed schema와 자연스럽게 결합해야 한다.
- 높음: async endpoint와 SSE streaming을 표준 HTTP 위에서 단순히 제공해야 한다.
- 높음: offline lane이 credential-free인 불변식을 깨지 않아야 한다.
- 중간: OpenAPI 문서와 `TestClient` 기반 테스트가 쉬워야 한다.
- 중간: 기존 CLI/RAG 모듈을 크게 재구성하지 않아야 한다.
- 낮음: full-stack admin UI나 template rendering은 이번 slice 범위가 아니다.

## 후보 비교

검증일: 2026-06-17. FastAPI 공식 문서는 Pydantic 모델 request/response,
async path operation, streaming response, `TestClient` 테스트 패턴을 제공한다.

| 기준 | FastAPI | Flask | Django/DRF | Starlette 직접 사용 |
|------|---------|-------|------------|---------------------|
| Pydantic schema | 기본 설계와 직접 결합 | 별도 validation 계층 필요 | serializer 체계가 별도 | 직접 조립 필요 |
| async/SSE | async endpoint와 ASGI 기반 streaming에 적합 | 가능하지만 확장/패턴 추가 필요 | 가능하지만 무겁고 설정량 큼 | 가능하지만 API schema 편의 낮음 |
| OpenAPI 문서 | 자동 생성 | 별도 확장 필요 | 가능하지만 DRF 의존/설정 큼 | 직접 구성 필요 |
| 테스트 | `TestClient` 공식 패턴 | 성숙 | 성숙 | 성숙 |
| repo 적합성 | 얇은 service layer에 적합 | typed API 어필 약함 | 이 repo에는 과한 웹 프레임워크 | FastAPI가 감싸는 저수준 선택지 |

## 결정

FastAPI를 채택한다. 이유는 최종 목표가 명시적으로 FastAPI/Pydantic async/SSE
service를 요구하고, 이 repo의 핵심인 typed RAG response/citation/gate evidence를
OpenAPI와 테스트 가능한 ASGI 표면으로 가장 작게 노출할 수 있기 때문이다.

이번 채택 범위는 다음으로 제한한다.

- `rfp_rag/service/` 아래 app factory, schema, route, SSE event helper 추가
- 기본 provider는 offline/index lane으로 두어 credential-free 테스트 유지
- `/healthz`, `/v1/answer`, `/v1/answer/stream`, `/v1/gates`만 제공
- dashboard, auth, background worker, cloud deployment는 별도 ADR/PR로 분리

## 탈락 사유

- Flask: 간단하지만 Pydantic/OpenAPI/async streaming을 포트폴리오 신호로 보여주기
  위해 추가 조립이 필요하다.
- Django/DRF: 강력하지만 이 repo의 단일 RAG API 표면에는 범위가 과하다.
- Starlette 직접 사용: 최소 ASGI 구현에는 좋지만 typed API 문서와 validation을
  FastAPI만큼 적은 코드로 얻기 어렵다.

## 재검토 조건

- FastAPI dependency가 RAG/eval dependency와 충돌해 offline lane을 깨는 경우
- 서비스 범위가 multi-tenant auth/admin UI로 커져 Django 계열이 더 적합해지는 경우
- SSE 대신 WebSocket 중심 실시간 UI가 핵심이 되어 별도 protocol design이 필요한 경우

## 출처

- Context7 `/fastapi/fastapi`, 2026-06-17: Pydantic model endpoint, async iterable
  streaming, dependency override and `TestClient` examples.
