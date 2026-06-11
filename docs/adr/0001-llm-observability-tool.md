# ADR-0001: LLM observability(트레이싱) 도구 선정

- 상태: 채택
- 날짜: 2026-06-11
- 결정자: Claude 제안 → 사용자 채택 (Langfuse)

## 배경

LangGraph agent lane의 노드별 실행 추적(라우팅 → 검색 → 재작성 루프 → HITL)을 시각화·디버깅할 observability 도구가 필요하다. 커리어 로드맵의 Eval/Tracing 항목이기도 하다. 당초 LangSmith MCP가 비교 없이 단독 추천되어, 본 ADR로 비교를 소급 수행한다. Claude Code에서 트레이스를 직접 조회(MCP)하는 워크플로우가 목표에 포함된다.

## 선택 기준

| 기준 | 가중치 | 근거 |
|------|--------|------|
| 무료 한도/비용 | 높음 | 개인 프로젝트, eval run을 반복 실행 |
| LangGraph 1.x 통합 난이도 | 높음 | 현재 스택이 LangChain/LangGraph |
| Self-hosting 가능성 | 중 | 데이터 주권 + 커리어 로드맵 "Cloud 배포" 항목과 시너지 (self-host 배포 자체가 포트폴리오) |
| Claude Code 연동(공식 MCP) | 중 | 트레이스 조회를 Claude Code 안에서 수행 |
| 유지보수 전망 | 중 | 장기 사용 전제 |
| 평가(eval) 기능 | 낮음 | ragas 기반 자체 게이트 보유 — 플랫폼 eval 의존도 낮음 |

## 후보 비교 (2026-06-11 웹 검증)

| 기준 | Langfuse | LangSmith | W&B Weave | Helicone |
|------|----------|-----------|-----------|----------|
| 라이선스 | MIT 오픈소스 | 클로즈드 SaaS | 클로즈드 | Apache 2.0 오픈소스 |
| Self-hosting | docker compose, 1급 지원 | **Enterprise 플랜 한정** | X | 가능(docker) — 단 아래 참조 |
| 무료 한도 | Cloud 50K units/월 + self-host 무제한 | 5K traces/월 (Developer) | 개인 무료 티어 (한도 미검증) | (미검증) |
| 유료 시작가 | $29/월 (Core) | $39/seat/월 (Plus) | (미검증) | (미검증) |
| LangGraph 통합 | `CallbackHandler` 1줄 (`config={"callbacks":[handler]}`) | 네이티브 — env var만으로 자동 추적 | 데코레이터/autopatch 방식 | proxy(base URL 교체) — 노드 수준 추적엔 부적합 |
| 프롬프트 관리 | O (강점) | O | 제한적 | X |
| 평가 기능 | datasets/scores/LLM-as-judge | 강력 (evals·annotation) | O (실험 비교 중심) | 제한적 |
| 비용 추적 | O | O | O (token/cost 자동 기록) | O (강점) |
| Claude Code 연동 | **공식 MCP(HTTP) + Observability 플러그인 + Agent Skill** | 공식 MCP (`uvx langsmith-mcp-server`) | 확인 안 됨 | 확인 안 됨 |
| 유지보수 전망 | 활발 | 활발 (LangChain) | 활발 | **2026-03 Mintlify 인수 후 maintenance mode — 신규 기능 중단** |

비고 (통념과 다른 검증 결과):
- Helicone은 "부분 오픈소스/self-host 불가"가 아니라 완전 OSS·self-host 가능이다. 탈락 사유는 라이선스가 아니라 **maintenance mode**.
- LangSmith self-hosting은 "불가"가 아니라 Enterprise 한정이다 — 개인 프로젝트 기준으로는 사실상 불가.

## 결정

**Langfuse 채택** — Cloud 무료 티어로 시작하고, 추후 self-host 전환을 별도 ADR로 검토한다.

이유: ① 무료 한도가 10배 (50K units vs 5K traces — eval run 반복에 여유), ② self-host 옵션이 로드맵의 Cloud 배포 항목과 시너지 (Cloud free로 시작 → self-host 전환을 후속 포트폴리오로), ③ Claude Code 연동 표면이 가장 두텁다 (MCP + 플러그인 + 스킬), ④ 프레임워크 독립적이라 LangChain 외 스택에도 재사용 가능. LangSmith의 우위(zero-config 통합, 채용 키워드 인지도)는 인정하나, CallbackHandler 1줄 차이와 키워드 노출은 ADR·README 기록으로 상쇄 가능.

## 탈락 사유

- Helicone: maintenance mode (Mintlify 인수, 신규 기능 중단) — 신규 채택 부적합. proxy 방식이라 LangGraph 노드 수준 추적에도 부적합.
- W&B Weave: ML 실험 추적이 본령, LLM 트레이싱은 보조적. self-host 불가, Claude Code 연동 부재.

## 재검토 조건

- Langfuse 무료 한도/가격 정책 변경, 또는 트레이스 볼륨이 50K units/월 초과
- LangSmith가 비엔터프라이즈 self-hosting 또는 대폭 확대된 무료 티어 제공
- 스택이 LangChain/LangGraph에서 이탈 (→ 프레임워크 독립 도구의 가치 상승)

## 출처

- [Langfuse vs LangSmith (Langfuse 공식 FAQ)](https://langfuse.com/faq/all/langsmith-alternative)
- [Langfuse vs LangSmith 독립 비교 (TECHSY)](https://techsy.io/en/blog/langfuse-vs-langsmith) · [leanware 비교](https://leanware.co/insights/langfuse-vs-langsmith)
- [Langfuse LangGraph 통합 가이드](https://langfuse.com/guides/cookbook/integration_langgraph) · [LangChain 콜백 문서](https://langfuse.com/integrations/frameworks/langchain)
- [Langfuse 공식 MCP Server](https://langfuse.com/docs/api-and-data-platform/features/mcp-server) · [Claude Code 연동](https://langfuse.com/integrations/other/claude-code) · [코딩 에이전트용 Langfuse](https://langfuse.com/agents)
- [Helicone GitHub (Apache 2.0)](https://github.com/Helicone/helicone) · [self-hosting 문서](https://docs.helicone.ai/getting-started/self-host/manual) · [maintenance mode 리뷰 (ChatForest)](https://chatforest.com/reviews/helicone-llm-observability-gateway/)
- [LangSmith MCP Server](https://github.com/langchain-ai/langsmith-mcp-server)
