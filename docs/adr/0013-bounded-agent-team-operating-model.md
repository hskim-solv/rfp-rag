# ADR-0013: Bounded Agent Team Operating Model

- 상태: 채택
- 날짜: 2026-06-17
- 결정자: 사용자 지시 후 Codex 적용

## 배경

RFP 프로젝트의 최종 목표는 production-grade Agentic RAG system이다. 구현 범위가
RAG 품질, real/open 평가, FastAPI service, LangGraph agent, ops tool, guardrails,
Docker/CI 문서까지 넓어졌기 때문에 단일 sequential agent만으로는 검토 병목이
생긴다.

Better Stack의 Anthropic C compiler agent-team 분석은 중앙 repository, isolated
workspace, task locking, filtered/fast test harness, external memory, specialized
roles가 multi-agent 작업을 가능하게 만든다고 정리한다. 다만 같은 글은 이 방식이
순수 자율이 아니라 human-guided automation이며, 많은 scaffolding과 비용을 전제로
한다고 평가한다.

이 repo는 real API 비용, ignored `artifacts/` gate evidence, embedded Qdrant
single-process 제약이 강하므로 16-agent autonomous loop를 그대로 도입하면 위험하다.

## 선택 기준

- 충돌 방지: 같은 파일, 같은 artifact, 같은 Qdrant path를 동시에 건드리지 않아야 한다.
- 비용 통제: `real_openai`, `pytest -m real`, canonical real index/eval 재생성은 중복 실행되면 안 된다.
- 검증 가능성: writer 결과는 main integrator가 통합 전 검증할 수 있어야 한다.
- 속도: 독립 구현, 긴 로그, 문서, 검증 후보 탐색은 병렬화해 main integrator의 대기 시간을 줄인다.
- 단순성: 새 daemon, persistent worker, Docker fleet 없이 현재 Codex 환경에서 실행 가능해야 한다.

## 후보 비교

| 기준 | 후보 A: 단일 agent만 사용 | 후보 B: full autonomous RALPH/Docker team | 후보 C: bounded multi-writer team |
|------|---------------------------|-------------------------------------------|----------------------------|
| 충돌 방지 | 높음 | 낮음: 별도 lock/merge infra 필요 | 중상: owner files/forbidden files로 write set 분리 |
| 비용 통제 | 높음 | 낮음: 병렬 real/API 실행 위험 | 높음: 비용/API는 main만 실행 |
| 속도 | 낮음 | 높음 | 높음: disjoint writer + read-only reviewer 병렬화 |
| 구현 부담 | 낮음 | 높음: Docker, task queue, lock, RALPH loop 필요 | 낮음: 기존 subagent + 지침으로 가능 |
| 이 repo 적합성 | 중간: 안전하지만 느림 | 낮음: artifacts/Qdrant/API 제약과 충돌 | 높음 |

## 결정

후보 C, bounded multi-writer team을 채택한다.

- main agent는 integrator/owner로 유지한다.
- disjoint write scope가 명확한 경우 writer subagent를 병렬 사용한다.
- read-only reviewer/explorer도 병렬 사용한다.
- 한 번에 활성 subagent는 기본 2개, 명확한 독립 구현 phase에서는 최대 3개까지 허용한다.
- 비용/API, canonical artifact, dependency/architecture 결정, shared contract 수정은 main integrator만 수행한다.

## 탈락 사유

- 후보 A: 안전하지만 문서 정합성, 실패 분석, 검증 후보 정리 같은 독립 작업까지 순차 처리해 속도 병목이 크다.
- 후보 B: 이 repo에는 아직 task lock, isolated worktree, filtered fast test harness, merge bot, cost governor가 없다. ignored gate artifacts와 embedded Qdrant 때문에 full autonomous parallel write가 위험하다.

## 운영 규칙

1. main integrator
   - 작업 분해, owner file 배정, artifact pipeline 실행, 비용/API 명령, commit/PR/merge 판단을 담당한다.
   - writer/reviewer 결과는 신뢰하되, 파일/명령/claim은 main이 최종 검증한다.

2. writer subagent
   - disjoint write scope가 명확할 때 사용한다.
   - prompt에는 owner files, allowed commands, forbidden files, forbidden artifacts, return contract를 포함한다.
   - 적합한 작업: FastAPI service skeleton, ops tool module, guardrail test module, docs/ADR slice처럼 파일 경계가 분리된 구현.
   - 금지: 같은 파일 공동 수정, `contracts.py`/`gate_status.py`/`evaluate.py` 같은 shared gate core 동시 수정, artifact pipeline 실행.

3. read-only subagent
   - 최대 2개까지 병렬 사용한다.
   - 적합한 작업: 실패/병목 분석, 문서 overclaim 스캔, 검증 명령 후보, ADR 후보 조사, PR 전 adversarial review.
   - 금지: 파일 수정, artifact 삭제/생성, real API 실행, dependency 설치, raw RFP/secret 노출.

4. task locking
   - 현재는 tool-level lock infra를 만들지 않는다.
   - 병렬 writer를 쓰는 경우 main prompt에 owner files, forbidden files, return contract를 명시한다.
   - full lock system은 Docker/worktree 기반 multi-worker를 실제 도입할 때 재검토한다.

5. test harness
   - narrow verification은 targeted tests와 `report_check`를 먼저 실행한다.
   - full `pytest -m "not real"`은 PR 전 또는 shared behavior 변경 후 실행한다.
   - real lane은 명시 승인 후 main agent만 candidate path부터 실행한다.

## 재검토 조건

- FastAPI/service, ops tool, guardrail, CI 작업이 서로 독립된 write set으로 분리되어 worker 병렬화 이득이 커질 때.
- Git worktree/Docker 기반 isolated workspace와 task lock을 repo-local로 도입할 때.
- real/open eval이 progress/resume/cost budget을 갖춰 병렬 smoke가 안전해질 때.
- subagent가 파일 충돌, artifact 손상, 비용 중복 실행을 일으켰을 때.

## 출처

- Better Stack, "Multi-Agent AI Development: How 16 Claude Agents Built a C Compiler", updated 2026-02-15, https://betterstack.com/community/guides/ai/anthropic-ai-agents-c-compiler/
