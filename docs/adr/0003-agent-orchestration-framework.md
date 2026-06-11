# ADR-0003: 에이전트 오케스트레이션 프레임워크 선정 (소급)

- 상태: 채택
- 날짜: 2026-06-11 (구현 선행 — agent lane 사이클에서 기 채택, 본 ADR로 비교를 소급 기록)
- 결정자: Claude 제안 → 사용자 승인

## 배경

agent lane은 route → retrieve → grade → rewrite(≤2회) → generate → verify 그래프에
HITL(저장 요청 시 interrupt 후 `--approve/--reject`로 재개)을 요구한다. 상태는 프로세스를
넘어 영속해야 한다 (같은 `--thread-id`로 승인 대기 재개). 이를 직접 구현할지,
프레임워크를 쓸지, 어느 프레임워크를 쓸지 결정이 필요했다.

## 선택 기준

| 기준 | 가중치 | 근거 |
|------|--------|------|
| HITL interrupt/재개의 1급 지원 | 높음 | CLI 프로세스 종료 후 재개가 핵심 시나리오 — 프레임워크 내장이어야 상태 버그 표면이 작다 |
| 상태 영속 (checkpointer) | 높음 | sqlite로 시작해 배포 시 Postgres 전환 경로 필요 |
| 세밀한 그래프 제어 | 높음 | 조건 분기(grade→rewrite), 루프 상한(rewrite ≤2), 결정론적 토폴로지 — eval 시나리오가 노드 단위로 매핑됨 |
| 기존 스택(LangChain) 정합 | 중 | rag_chain·providers가 langchain-core 기반 |
| 라이선스·안정성 | 중 | MIT/Apache + 1.0 이상 안정판 |

## 후보 비교 (2026-06-11 웹 검증)

| 기준 | LangGraph | LlamaIndex Workflows | CrewAI | AutoGen |
|------|-----------|----------------------|--------|---------|
| HITL 패턴 | `interrupt()` → `Command(resume=...)` — 1급 프리미티브 | `ctx.wait_for_event(HumanResponseEvent)` — 이벤트 기반 | 1급 개념으로 부각되지 않음 | (후속 프레임워크로 이관) |
| 상태 영속 | SqliteSaver/PostgresSaver **공식 패키지**, thread_id 재개 | `WorkflowCheckpointer` 래퍼 (네이티브 통합 아님) | 공식 체크포인터 패키지 없음 | - |
| 그래프 제어 | StateGraph — 조건 엣지·루프 명시 | 이벤트 흐름 (그래프 명시성 낮음) | role 기반 협업 추상화 (high-level) | - |
| LangChain 정합 | 동일 생태계 (langchain-ai) | 별도 생태계 | 별도 | - |
| 라이선스 / 안정성 | MIT / 1.0 (2025-10-17), 현재 1.2.4 | MIT | MIT | **maintenance mode** — Microsoft Agent Framework로 이관 |

## 결정

**LangGraph** — HITL interrupt/재개와 checkpointer가 프레임워크 1급 개념이라 직접 구현 대비
상태 관리 버그 표면이 작고, StateGraph의 명시적 토폴로지 덕에 eval 시나리오(`evaluate_agent.py`)가
노드 단위로 결정론적으로 매핑된다. sqlite → Postgres checkpointer 전환 경로도 공식 패키지로 존재한다.

## 탈락 사유

- LlamaIndex Workflows: HITL이 이벤트 대기 방식이고 체크포인트가 래퍼 — 가능은 하나 1급이 아니어서
  "프로세스 종료 후 CLI 재개" 시나리오의 구현 부담이 큼. 기존 LangChain 스택과 생태계도 갈라짐.
- CrewAI: role 기반 멀티에이전트 협업용 — 단일 에이전트의 세밀한 그래프 제어·interrupt 재개가 용도와 불일치.
- AutoGen: maintenance mode (Microsoft Agent Framework로 이관) — 신규 채택 부적합.
- 직접 구현: 루프 상한·분기는 가능하나 interrupt 후 영속·재개를 만들면 사실상 미니 LangGraph를 재발명.

## 재검토 조건

- Microsoft Agent Framework 성숙 (durability·time-travel 등 LangGraph 수준 기능 확인됨 — 멀티에이전트 확장 시 재비교)
- LangGraph OSS와 유료 LangGraph Platform의 경계 변화 (OSS 기능 축소 시)
- 멀티에이전트 협업 패턴이 필요해질 때 (CrewAI 재평가)

## 출처

- https://github.com/langchain-ai/langgraph (interrupt/Command, LICENSE, releases)
- https://github.com/langchain-ai/langgraph/tree/main/libs/checkpoint-sqlite / checkpoint-postgres
- https://pypi.org/project/langgraph
- https://github.com/run-llama/llama_index (Workflows — wait_for_event, WorkflowCheckpointer)
- https://github.com/crewAIInc/crewAI
- https://github.com/microsoft/autogen (maintenance mode 배지), https://github.com/microsoft/agent-framework
