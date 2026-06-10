# Real Provider 품질 레인 설계 (LangChain 기반)

- 날짜: 2026-06-10
- 상태: 사용자 설계 승인 완료, 구현 계획 수립 전
- 선행 산출물: `rfp-rag-offline-v1` 계약 기반 CSV-first RAG baseline (REPORT.md 참조)

## 1. 목표

입찰 RFP 100건 corpus에 대해 OpenAI embedding/generation 기반 real RAG 레인을 구축하고,
기존 55건 평가 세트 + RAGAS judge로 semantic 품질을 측정하여 `rag_quality_complete` 게이트를
판정 가능하게 만든다.

부가 목표(사용자 명시): 취업 포트폴리오 관점에서 LLM/RAG 엔지니어 기술 스택
(LangChain, Qdrant, OpenAI API, RAGAS) 활용 경험을 어필할 수 있는 구조로 구현한다.

## 2. 확정된 의사결정

| 결정 항목 | 선택 | 근거 |
|---|---|---|
| Provider | OpenAI API (`OPENAI_API_KEY` 보유) | 구현 단순성, embedding+generation 일원화 |
| Vector store | Qdrant 로컬 모드 (서버리스, 디스크 persist) | 페이로드 필터 확장성, Docker 서버 전환 경로, 포트폴리오 가치 |
| Retrieval 스코프 | Dense-only | baseline 수치 먼저 확보, hybrid는 다음 사이클 |
| 평가 | 기존 55건 세트 재평가 + RAGAS judge (faithfulness, answer_relevancy) | 가이드의 "평가 방식 직접 선정" 요구 충족 |
| 구현 접근 | LangChain 기반, 인터페이스 통합 (A안) | 표준 인터페이스로 fake/real 동일 파이프라인, 오프라인 CI 유지 |

## 3. 아키텍처

단일 LangChain 파이프라인에 두 레인이 구현체 주입으로 갈라진다.

```
                    ┌─ offline 레인: LexicalHashEmbeddings + TemplateAnswerGenerator
CSV → 청킹(기존) → LangChain 파이프라인 ─ Qdrant 로컬 모드 → 평가(55건, 기존 메트릭)
                    └─ real 레인:   OpenAIEmbeddings + ChatOpenAI(+RAGAS judge)
```

- **offline 레인**: API 키 없이 전체 재현. 기존 `offline_scaffold_complete` 게이트 유지.
  pytest/CI의 기본 레인.
- **real 레인**: OpenAI embedding/generation + RAGAS judge. `thresholds_applied=true`로
  `rag_quality_complete` 판정. 이번 사이클의 목표물.

### 핵심 설계 판단 두 가지

**(1) 커스텀 `LexicalHashEmbeddings`.** LangChain 내장 `FakeEmbeddings`는 랜덤 벡터라
검색 의미가 사라져 abstention(낮은 유사도 → 거절) 계약 검증이 불가능하다. 기존
`fake_provider.py`의 한국어 n-gram lexical 피처를 hashing trick으로 고정 차원 벡터화한
커스텀 `Embeddings` 구현체를 만들어, offline 레인에서도 검색·abstention이 실제로
동작하게 한다. 기존 자산의 LangChain 인터페이스 이식이다.

**(2) 자체 `AnswerGenerator` 인터페이스.** LangChain 테스트 더블(`FakeListChatModel`)은
고정 응답만 반환해 citation 계약 검증에 부적합하다. generation 단계만 작은 자체
인터페이스로 두고, real 구현은 `ChatOpenAI` + `with_structured_output`(citation 스키마
강제), offline 구현은 기존 `ask.py` 템플릿 로직을 이식한다. 표준 인터페이스가 있는 곳
(Embeddings/VectorStore)은 프레임워크를 쓰고, 도메인 로직은 자체 인터페이스로 절제한다.

## 4. 컴포넌트

### 신규 모듈

| 모듈 | 역할 |
|---|---|
| `rfp_rag/providers.py` | 레인별 `Embeddings`/`AnswerGenerator` 팩토리. `LexicalHashEmbeddings`, `TemplateAnswerGenerator`, `LLMAnswerGenerator` |
| `rfp_rag/vector_index.py` | `QdrantVectorStore` 빌드/로드. 로컬 모드 디스크 persist(`artifacts/index/qdrant/`), chunk_id→UUID5 포인트 ID 매핑, payload에 기존 메타데이터 전부 보존 |
| `rfp_rag/rag_chain.py` | retrieve(top-k + min_score 게이트) → generate 조합. 기존 응답 JSON 스키마(`answer/sources/warnings/confidence/retrieved_doc_ids/retrieved_chunk_ids/scores`) 그대로 유지 |
| `rfp_rag/judge.py` | RAGAS `faithfulness`/`answer_relevancy` 래퍼 (real 전용) |

### 레인 식별자 통일 규칙

레인 식별자는 전역에서 `offline` | `real_openai` 두 개로 통일한다. 기존 CLI 값
`fake`(build_index)와 `fake_offline`(evaluate)은 하위 호환 별칭으로 계속 받아들이되,
아티팩트(manifest, metrics, contract)에는 통일된 식별자만 기록한다.

### 수정 모듈

- `build_index.py` — `--embedding-provider {offline,openai}`. Qdrant 인덱싱 경로로 교체.
  `manifest.json`(모델명·차원·레인 기록)과 `chunks.jsonl`(감사용)은 계속 생성.
- `ask.py` — `rag_chain` 호출로 변경, `--provider` 플래그 추가.
- `evaluate.py` — 레인 분기. real이면 RAGAS 메트릭 추가 + 임계값 적용 +
  `rag_quality_complete` 판정.
- `contracts.py` — `rfp-rag-real-v1` 계약 추가 (required commands, 게이트 의미론,
  임계값 사후 조정 시 보고서 기록 원칙 포함).

### 보존되는 것

청킹 로직과 chunk ID 규칙(`doc:{csv_row_id}:chunk:{n}`), corpus 검증, 55건 평가 세트
생성 로직, 메트릭 정의(recall@k, MRR, citation presence/validity, metadata exact match,
abstention), `report_check` 게이트. LangChain으로 바뀌는 것은 임베딩·저장·검색·생성
실행부이며, 데이터 계약과 평가 자산은 그대로다.

## 5. 데이터 흐름

1. **build**: CSV → corpus 검증 → 청킹 → LangChain `Document` 변환(chunk_id·메타데이터
   보존) → `embed_documents` → Qdrant 컬렉션(레인별 분리) + manifest.
2. **ask**: 질문 → `embed_query` → Qdrant top-k 검색 → top 스코어 < min_score면
   abstain("없는 정보" + `insufficient_context` warning + confidence=low + sources 빈 배열)
   → 아니면 `AnswerGenerator`가 인용 포함 답변 생성.
3. **evaluate**: 55건 생성(golden metadata 40 + curated text 10 + abstention 5) → 각각
   ask → 기존 메트릭 채점 → real이면 RAGAS judge 추가 → `metrics.json` /
   `predictions.jsonl` / `report.md` → 게이트 판정.

### 모델 기본값

전부 config/CLI로 교체 가능. 정확한 최신 모델명·버전 핀은 구현 단계에서 공식 문서로
확인 후 확정한다.

- 임베딩: `text-embedding-3-small` (1536차원)
- 생성: 소형 모델 (gpt-4o-mini급)
- judge: 생성 모델보다 한 단계 상위 모델
- 1회 풀 사이클(인덱싱 + 평가 55건 + judge) 비용 추정: $1 미만

### abstention 재캘리브레이션 (real 레인)

real embedding의 cosine 분포는 lexical과 다르므로 기존 `min_score=0.25`를 그대로 쓰지
않는다. 평가 실행 시 in-domain vs abstention 질문의 스코어 분포를 `metrics.json`에
기록하고 그것을 근거로 임계값을 정한다. 동시에 LLM 프롬프트에 "근거 불충분 시
'없는 정보'로 답하라"를 지시해 이중 방어한다.

## 6. 에러 처리

- **API 키 부재**: real 레인 명령은 실행 시작 시점에 즉시 명확한 에러로 중단.
  메시지: "OPENAI_API_KEY required for real lane (offline lane runs without credentials)".
- **OpenAI 호출 실패**: 임베딩은 배치 단위 재시도(SDK 내장 백오프 활용). 평가 중 개별
  질문 실패는 해당 질문만 `error` 상태로 기록하고 계속 진행. 실패율 10% 초과 시
  `evaluation_valid=false`로 평가 자체를 무효 처리해 불완전한 수치의 게이트 통과 주장을
  차단.
- **RAGAS judge 실패**: judge 메트릭만 null + warning 기록. retrieval·citation 게이트는
  judge와 독립적으로 판정.
- **Qdrant 로컬 모드 제약**: 단일 프로세스 전용(동시 접근 불가)을 README에 명시.
  프로덕션 전환 시 Docker 서버 교체 경로 문서화.
- **재현성**: `predictions.jsonl`·`manifest.json`에 모델명, 임베딩 차원, top_k, min_score
  기록.

## 7. 테스트 전략

- **offline 레인 = 기본 테스트 레인**: 전체 pytest가 API 키 없이 통과.
  `LexicalHashEmbeddings` + `TemplateAnswerGenerator` + Qdrant in-memory로
  build → ask → evaluate → report_check e2e 검증. 기존 테스트를 LangChain 파이프라인
  대상으로 이식.
- **단위 테스트**: ① `LexicalHashEmbeddings` 결정론성(같은 텍스트→같은 벡터)
  ② Document 변환 시 chunk_id/메타데이터 보존 ③ min_score abstention 동작
  ④ 응답 JSON 스키마 ⑤ `rag_quality_complete` 판정 로직(mock 메트릭으로 임계값 경계
  검증).
- **real 레인 스모크**: `@pytest.mark.real` 마커 — 키가 있을 때만 1~2건 실호출,
  CI에서는 자동 skip.

## 8. 성공 기준 (게이트)

| 게이트 | 조건 | 레인 |
|---|---|---|
| `offline_scaffold_complete` | citation presence ≥ 0.95, citation validity ≥ 0.90, abstention ≥ 0.90 (기존 그대로) | offline |
| `rag_quality_complete` | 기존 `REAL_QUALITY_THRESHOLDS` 전체: recall@3 ≥ 0.85, recall@5 ≥ 0.90, citation presence ≥ 0.95, citation validity ≥ 0.90, metadata exact match ≥ 0.90, abstention ≥ 0.90 + 신규: RAGAS faithfulness ≥ 0.80, answer_relevancy ≥ 0.70 | real |

RAGAS 임계값 두 개는 제안 수치다. 첫 실행에서 분포를 보고 조정할 수 있되, 조정 시
근거를 보고서에 기록한다는 원칙을 `rfp-rag-real-v1` 계약에 명시한다.

## 9. 의존성

`langchain-core`, `langchain-openai`, `langchain-qdrant`, `qdrant-client`, `ragas`.
정확한 버전 핀은 구현 단계에서 공식 문서 확인 후 `pyproject.toml`에 추가.

## 10. 스코프 제외 (다음 사이클 확장 경로)

- hybrid/BM25 검색, RRF, 청킹 비교 실험 — Qdrant sparse vector 네이티브 지원으로
  추가 비용 낮음
- LangGraph 기반 agentic RAG (query rewrite, self-correction) — "Agent AI 엔지니어"
  어필 경로
- 원문 HWP/PDF 파싱 (현재는 CSV `텍스트` 컬럼이 source of truth)
- 데모 UI (Streamlit/FastAPI)
