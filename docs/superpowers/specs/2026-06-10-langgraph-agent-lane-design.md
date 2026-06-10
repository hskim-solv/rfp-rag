# LangGraph Stateful Multi-step Agent 레인 설계

- 날짜: 2026-06-10
- 상태: 자율 사이클 — 설계 근거는 사용자 승인 갭 목록(메모리 `ai-agent-engineer-career-target`) 1순위 + 이전 설계 문서 §10 확장 경로. 최종 승인은 PR 리뷰 게이트로 받는다.
- 선행 산출물: `rfp-rag-real-v1` 계약 기반 real provider 품질 레인 (`rag_quality_complete=true`, PR #1 머지)

## 1. 목표

기존 단발 RAG 체인(`rag_chain.py`: retrieve → generate)을 LangGraph `StateGraph` 기반
**stateful multi-step agent**로 확장한다. 채용 키워드 매핑(메모리 갭 목록) 기준:

- **갭 1 (LangGraph stateful multi-step agent)**: planner/router, retriever, tool executor,
  evaluator(grade), retry·fallback(rewrite 루프), human approval 노드 — 전부 명시적 노드로 구현.
- **갭 2 (tool calling 업무 자동화) 부분 커버**: agent가 검색·메타데이터 집계·보고서 저장
  도구를 호출하고, 쓰기 도구는 권한 게이트(승인) + audit log를 남긴다.
- **갭 6 (guardrail/HITL) 부분 커버**: `interrupt()` 기반 승인 흐름 + rewrite 횟수 상한 +
  인용 검증 fallback.

이력서 한 줄 목표: "LangGraph 기반 stateful multi-step agent 설계·구현 — 라우팅/자가교정
검색 루프/도구 호출/HITL 승인을 명시적 그래프로 구성, 시나리오 평가 게이트로 검증."

## 2. 접근법 비교

| 접근법 | 내용 | 판단 |
|---|---|---|
| A. prebuilt ReAct agent (`create_react_agent`) | 도구만 바인딩하면 루프는 프레임워크가 처리 | 빠르지만 제어 흐름이 블랙박스. "stateful multi-step 설계" 어필 불가, 오프라인 결정론 테스트 어려움. 기각 |
| **B. 커스텀 `StateGraph` — 명시적 노드/조건 엣지 (채택)** | route → retrieve → grade → rewrite 루프 → generate → verify를 직접 설계 | LangGraph 핵심 개념(State, conditional edges, checkpointer, interrupt) 전부 사용. 메모리 갭 1의 노드 목록과 1:1 대응. 기존 레인 주입 패턴 유지 가능 |
| C. supervisor 멀티에이전트 | 서브그래프 + supervisor 라우팅 | corpus 100건/단일 도메인에 과잉. YAGNI. 기각 |

## 3. 아키텍처

이전 사이클의 레인 철학을 그대로 확장한다: **그래프 구조는 하나, 노드 내부 두뇌(LLM
호출부)만 레인별 구현체 주입**. 따라서 그래프 토폴로지·state 전이·interrupt·checkpointer
전부가 API 키 없이 오프라인으로 테스트된다.

```
START → route ── metadata_query ──→ tool_exec(aggregate_metadata) ──→ generate
            └─── rag_query ───────→ retrieve → grade ── sufficient ──→ generate
                                       ▲          └─ insufficient → rewrite (≤2회) ─┐
                                       └─────────────────────────────────────────────┘
                                                  └─ retries exhausted → abstain → END
generate → verify ── citations ok ──→ (save_requested? → save_report) → respond → END
              └─ invalid → regenerate(1회) → verify → (재실패 시 abstain)
```

- `route`는 질의 유형(rag/metadata)과 **저장 요청 여부**(`save_requested`)를 함께
  추출한다 (예: "...정리해서 보고서로 저장해줘"). 두 축은 직교 — 어떤 경로든 답변
  확정 후 `save_requested=true`면 `save_report` 노드를 경유한다.
- `save_report` 노드는 도구 내부에서 `interrupt()`로 일시정지 → 승인 시 저장 +
  audit log, 거부 시 취소를 audit log에 기록하고 답변만 반환한다.
- metadata 경로의 `generate`: 집계 결과(rows/합계)를 답변으로 포맷한다. **양 레인 공통
  결정론 포맷터**를 사용한다 (구현 중 단순화 결정 — LLM 포맷팅은 결정론 채점을 깨고
  비용만 늘린다). 인용(`sources`)은 집계에 사용된 CSV row의 doc_id 목록으로 구성해
  기존 응답 스키마를 유지한다.

### 노드 책임 (메모리 갭 1 노드 목록 대응)

| 노드 | 역할 | offline 구현 | real 구현 |
|---|---|---|---|
| `route` (planner) | 질문을 `rag_query` / `metadata_query`로 분류 | 규칙 기반 (집계·정렬·건수 키워드) | LLM structured output 분류 |
| `retrieve` | 기존 `vector_index.search` 재사용 (top-k) | 동일 (LexicalHashEmbeddings) | 동일 (OpenAIEmbeddings) |
| `grade` (evaluator) | 검색 충분성 판정 | top score ≥ min_score (기존 로직) | 동일 스코어 게이트 (LLM grader는 스코프 제외 — §9) |
| `rewrite` (retry·fallback) | 검색 실패 시 질의 재작성 후 재검색, 최대 2회 | 결정론적 변형 (조사 제거·핵심명사 추출) | LLM 질의 재작성 |
| `tool_exec` | `aggregate_metadata` 실행 | 레인 공통 (순수 CSV 연산, LLM 불필요) | 동일 |
| `generate` | 인용 포함 답변 생성 | 기존 `TemplateAnswerGenerator` | 기존 `LLMAnswerGenerator` |
| `verify` | 인용 유효성 검증 (기존 citation validity 로직 이식) | 레인 공통 | 동일 |
| `abstain` | 기존 abstention 응답 포맷 재사용 | 레인 공통 | 동일 |

### State

```python
class AgentState(TypedDict):
    question: str            # 현재 (재작성된) 질의
    original_question: str
    route: str               # rag_query | metadata_query
    save_requested: bool     # 보고서 저장 요청 여부 (route에서 추출)
    results: list[...]       # 검색 결과 (SearchResult 직렬화)
    rewrite_count: int
    tool_calls: list[dict]   # audit 기록용 도구 호출 이력
    answer: dict | None      # 기존 응답 JSON 스키마 그대로
    outcome: str             # answered | abstained | rejected
```

응답 JSON 스키마(`answer/sources/warnings/confidence/...`)는 기존 계약을 그대로 유지하고,
agent 레인은 `route/rewrite_count/tool_calls/outcome`을 추가 필드로 감싼다.

### Stateful 영속 + HITL

- **checkpointer**: 기본 `MemorySaver`(테스트), CLI는 `SqliteSaver`
  (`artifacts/agent/checkpoints.sqlite`) — thread_id 기반 멀티턴 상태 유지·재개.
- **human approval**: `save_report` 도구 내부에서 `interrupt()` 호출. CLI가 interrupt
  payload(저장 경로·내용 미리보기)를 출력하고 사용자 승인/거부 입력으로
  `Command(resume=...)` 재개. 테스트에서는 resume 값을 주입해 양 분기 검증.

## 4. 도구 (tool calling)

| 도구 | 권한 | 설명 |
|---|---|---|
| `search_rfp(query, top_k)` | 읽기, 자유 | 기존 벡터 검색 래핑 |
| `aggregate_metadata(filters, sort_by, top_n, agg)` | 읽기, 자유 | `data_list.csv` 메타데이터 질의: 사업 금액/발주 기관/마감일 필터·정렬·건수·합계. pandas 없이 stdlib csv로 구현 (의존성 최소화) |
| `save_report(filename, content)` | **쓰기, interrupt 승인 필수** | `deliverables/agent_reports/` 하위에만 저장 (경로 탈출 차단). 승인/거부 모두 audit log 기록 |

**audit log**: 모든 도구 호출을 `artifacts/agent/audit.jsonl`에 append
(`ts, thread_id, tool, args, outcome, approved`). 갭 2의 "권한 체크 + audit log" 증거.

## 5. 모듈 구성

기존 flat 구조에서 agent만 서브패키지로 분리한다 (파일 5개 이상, 응집 단위가 다름).

| 모듈 | 역할 |
|---|---|
| `rfp_rag/agent/state.py` | `AgentState`, 라우트/outcome 리터럴 |
| `rfp_rag/agent/brains.py` | 레인별 두뇌 인터페이스: `Router`, `QueryRewriter` (offline 규칙 기반 / real LLM 구현) |
| `rfp_rag/agent/tools.py` | 도구 3종 + audit logger |
| `rfp_rag/agent/nodes.py` | 노드 함수 (state in → partial state out) |
| `rfp_rag/agent/graph.py` | `StateGraph` 조립, conditional edges, checkpointer 팩토리 |
| `rfp_rag/agent/run_agent.py` | CLI: `--provider`, `--thread-id`, interrupt 승인 프롬프트, resume |
| `rfp_rag/agent/evaluate_agent.py` | agent 시나리오 평가 + `agent_lane_complete` 판정 |
| `contracts.py` (수정) | `rfp-agent-v1` 계약 추가 |

기존 모듈(`rag_chain.py`, `providers.py`, `vector_index.py`, `evaluate.py`)은 수정하지
않는다 — agent 레인은 이들을 호출만 한다. 단발 RAG CLI(`ask.py`)와 기존 게이트는 그대로
유지된다 (회귀 없음).

## 6. 평가 / 게이트 (`agent_lane_complete`)

agent 전용 시나리오 세트 (offline 레인 판정 + real 스모크):

| 시나리오 그룹 | 건수 | 메트릭 | 임계값 |
|---|---|---|---|
| 라우팅: rag vs metadata 질문 분류 | 20 (각 10) | routing accuracy | ≥ 0.90 |
| 단순 RAG 회귀: 기존 golden 세트 서브셋 | 20 | citation presence/validity, exact match | 기존 real 레인 임계값 동일 |
| rewrite 루프: 1회 재작성으로 회복 가능한 질의 | 5 | 회복률 + 루프 종료(≤2회) 보장 | 회복 ≥ 0.6, 종료 1.0 |
| abstention 유지 | 10 (기존 세트) | abstention accuracy | ≥ 0.90 |
| 도구 호출: aggregate_metadata 인자 정확도 | 10 | 기대 결과 일치(결정론 채점) | ≥ 0.90 |
| HITL: save_report 승인/거부/audit | 시나리오 테스트 | 승인 시에만 파일 생성, audit 완전성 | 1.0 (계약 테스트) |

- **offline 레인이 게이트 판정 레인**이다 — 그래프 로직·도구·HITL은 결정론적이므로
  오프라인 판정이 유효하다. real 레인은 routing/rewrite 두뇌 스모크(`@pytest.mark.real`
  + 소규모 평가 실행)로 보강하고 결과를 REPORT에 기록한다.
- real LLM 라우팅 정확도가 offline 규칙과 다르게 나오면 임계값 조정 대신 프롬프트를
  수정하고, 조정이 불가피하면 근거를 보고서에 기록한다 (이전 사이클 원칙 승계).

## 7. 에러 처리

- **루프 종료 보장**: rewrite ≤ 2회, regenerate ≤ 1회 — state 카운터로 강제, 초과 시 abstain.
  LangGraph `recursion_limit`을 안전망으로 추가 설정.
- **도구 실패**: 도구 예외는 ToolMessage 에러로 변환해 state에 기록, agent는 abstain
  fallback. `save_report` 경로 검증 실패는 즉시 거부 + audit.
- **API 키 부재**: real 레인 명령은 시작 시점 즉시 중단 (기존 메시지 규칙 재사용).
- **checkpointer 손상/부재**: thread 재개 실패 시 새 thread로 시작하라는 명확한 에러.
- **재현성**: audit.jsonl + checkpoint + 평가 manifest에 모델명·레인·임계값 기록.

## 8. 테스트 전략

이전 사이클과 동일하게 offline = 기본 pytest 레인 (API 키 없이 전체 통과):

1. 노드 단위: route 분류 규칙, grade 경계(min_score), rewrite 변형·카운터, verify 인용 검증
2. 도구 단위: aggregate_metadata 필터/정렬/집계 정확성, save_report 경로 차단·audit 기록
3. 그래프 통합: in-memory 인덱스로 end-to-end — 5개 경로 각각
   (직답 / rewrite 후 회복 / 소진 후 abstain / metadata 라우트 / HITL 승인·거부)
4. interrupt/resume: `Command(resume=...)` 양 분기, checkpointer thread 재개
5. real 스모크: `@pytest.mark.real` — LLM router/rewriter 1~2건

## 9. 스코프 제외 (다음 사이클)

- LLM grader (검색 결과 관련성 LLM 판정) — 현재는 스코어 게이트로 충분, judge 비용 회피
- Langfuse/LangSmith tracing (갭 3) — 다음 사이클 1순위 후보
- FastAPI/Docker 배포 (갭 5), hybrid search (갭 4), MCP 도구 (갭 7)
- multi-turn 대화 메모리 활용 질의 (checkpointer 인프라는 이번에 깔리지만 대화형 평가는 제외)

## 10. 의존성

`langgraph>=1.0`, `langgraph-checkpoint-sqlite`. 정확한 버전 핀은 구현 단계에서 확인 후
`pyproject.toml`에 추가. 신규 모델 호출 없음 — real 두뇌는 기존 `ChatOpenAI` 소형 모델
재사용, judge 불필요(결정론 채점)이므로 **이번 사이클 real API 비용은 routing/rewrite
스모크 + 소규모 real 평가로 $1 미만 추정**.
