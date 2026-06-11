# ADR-0004: 벡터 스토어 선정 (소급)

- 상태: 채택
- 날짜: 2026-06-11 (구현 선행 — offline lane 사이클에서 기 채택, 본 ADR로 비교를 소급 기록)
- 결정자: Claude 제안 → 사용자 승인

## 배경

RFP 100건의 청크 인덱스를 저장·검색할 벡터 스토어가 필요하다. 제약: 로컬 개발은 서버
프로세스 없이(임베디드) 돌아가야 하고, 배포 시 서버 모드로 코드 변경 없이 전환할 수 있어야
한다 (커리어 로드맵 "Cloud 배포"). doc_id 기반 payload 필터도 사용한다.

## 선택 기준

| 기준 | 가중치 | 근거 |
|------|--------|------|
| 임베디드 → 서버 무변경 전환 | 높음 | offline/real lane 공통 코드 + 배포 로드맵 |
| 메타데이터(payload) 필터 | 높음 | doc_id 스코핑, metadata_query 라우트 |
| LangChain 공식 통합 | 중 | rag_chain이 langchain 기반 (`langchain-qdrant`) |
| 라이선스 | 중 | OSS 우선 |
| 검색 품질 확장 경로 | 낮음 | 하이브리드 검색(RRF) 등 — 당장은 미사용 |

## 후보 비교 (2026-06-11 웹 검증)

| 기준 | Qdrant | Chroma | FAISS |
|------|--------|--------|-------|
| 임베디드 모드 | O (`QdrantClient(path=...)`) | O (`chromadb.Client()`) | 라이브러리 자체가 인프로세스 |
| 서버 모드 / 전환 | O — **동일 클라이언트 API, 초기화 인자만 변경** | O (`chroma run`) — 통일 API 지향 (전환 시 API 차이는 미검증) | X — 서버 없음, 직접 구축 |
| payload/메타데이터 필터 | O (`Filter`/`FieldCondition`/`Range`) | O | X — 직접 구현 필요 |
| LangChain 공식 통합 | `langchain-qdrant` (공식 partner 패키지) | `langchain-chroma` | 커뮤니티 통합 |
| 영속화 | O | O | 인덱스 파일 직렬화 직접 관리 |
| 라이선스 | Apache-2.0 | Apache-2.0 | MIT |
| 확장 경로 | 하이브리드 검색(RRF/DBSF), 분산 서버 | 1.x로 성숙 중 | 검색 커널로서는 최고 성능 계열 |

비고:
- 임베디드 모드의 **단일 프로세스 잠금 제약은 공식 문서에서 미확인(미검증)** — 단 본 프로젝트에서
  동시 접근 시 잠금 충돌을 실제로 경험했고 운영 규칙으로 기록되어 있다 (CLAUDE.md Conventions).
- Chroma는 결정적 결함으로 탈락한 것이 아니다 — 아래 탈락 사유 참조.

## 결정

**Qdrant** — 임베디드와 서버가 동일 클라이언트 API라 lane 전환·배포 전환에 코드 변경이 없고,
payload 필터와 `langchain-qdrant` 공식 통합이 현재 구조(`vector_index.py`)에 그대로 맞는다.
하이브리드 검색·분산 등 프로덕션 확장 경로가 명확해 로드맵(프로덕션 벡터 DB 운영 경험)과도 정합.

## 탈락 사유

- Chroma: 임베디드+서버 지원으로 **대등한 후보**. 선택을 가른 것은 Qdrant의 프로덕션 확장 경로
  (하이브리드 검색, 분산)와 필터 표현력 — 결함 탈락이 아니라 우선순위 차이.
- FAISS: 검색 라이브러리일 뿐 영속화·필터·서버를 직접 구축해야 함 — "서버 전환 경로" 기준 미달.

## 재검토 조건

- 멀티프로세스 동시 접근이 상시 필요해질 때 (임베디드 잠금 충돌 — 서버 모드 전환 시점)
- 인덱스 규모가 임베디드 모드 한계를 넘을 때
- Chroma 서버 모드의 프로덕션 기능(스케일·필터)이 Qdrant와 대등해질 때

## 출처

- https://github.com/qdrant/qdrant-client (README — local mode/서버 동일 코드, Filter 모델)
- https://pypi.org/pypi/langchain-qdrant/ , https://github.com/langchain-ai/langchain/tree/master/libs/partners/qdrant
- https://github.com/chroma-core/chroma (README — in-memory/client-server, LICENSE)
- https://github.com/facebookresearch/faiss (README — "library for efficient similarity search")
