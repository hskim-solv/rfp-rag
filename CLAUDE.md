# rfp-rag

입찰 RFP 100건의 원본 HWP/PDF 파싱 artifacts를 RAG 본문 source of truth로 쓰는 RAG + LangGraph agent. CSV는 사업명·발주기관·예산·마감일·파일명 metadata registry로만 사용한다. 상세 명세·명령어는 README.md, 사이클 결과·보정 근거는 REPORT.md.

## Lanes & gates (핵심 불변식)

- **offline lane은 credential-free**: `python3 -m pytest -m "not real"` 은 OPENAI_API_KEY 없이 항상 통과해야 한다. 깨면 회귀다.
- **real lane은 비용 발생** (풀 사이클 ~$5, judge가 지배적): `--provider real_openai` 평가, `pytest -m real`, real 인덱스 빌드는 사용자가 명시적으로 요청할 때만 실행한다.
- 게이트 위치: `artifacts/eval/metrics.json` → `offline_scaffold_complete` / `artifacts/eval_real/metrics.json` → `rag_quality_complete` / `artifacts/eval_agent/metrics.json` → `agent_lane_complete`. 실행·판정 절차는 `/eval-lane` 스킬 참조.
- **artifacts/ 는 게이트 증거**: 손으로 편집하지 않는다. 항상 파이프라인 재실행으로 갱신한다 (gitignore 대상이지만 로컬 증거로 보존).
- `--min-score` 는 lane별 보정값 (source-first offline 0.34 / real 0.47). 변경하려면 `metrics.json`의 `score_distribution` 근거를 REPORT.md에 기록한다.

## Architecture

- `rfp_rag/`: corpus → chunking → vector_index(embedded Qdrant) → rag_chain → evaluate/judge → report_check. 외부 호출은 전부 `providers.py` 추상화 뒤에 두고, offline lane은 `fake_provider.py`로 대체한다.
- `rfp_rag/tracing.py`: LANGFUSE_* 키 존재 시에만 Langfuse CallbackHandler 주입 (키 없으면 no-op — credential-free 불변식 유지). 핸들러는 프로세스당 1개 캐시, CLI 종료 경로는 try/finally로 flush.
- `rfp_rag/agent/`: LangGraph StateGraph — route → retrieve → grade → rewrite(≤2회) → generate → verify → (저장 요청 시) HITL interrupt. 그래프 토폴로지는 lane 공통, `brains.py`의 Router/Rewriter만 lane별 주입.
- contracts: `rfp-rag-offline-v4` / `rfp-rag-real-v6` / `rfp-rag-open-v4` / `rfp-agent-v2`. 계약 필드를 바꾸면 contract 버전 bump + `tests/test_gates.py` 동기화가 필수다.
- agent 부산물: tool 호출은 `<artifacts>/audit.jsonl`에 기록, 상태는 `<artifacts>/checkpoints.sqlite`에 영속 (같은 `--thread-id`로 HITL 승인 대기 재개).

## Conventions

- Python 3.11+, ruff (format + `check --fix`). `.py` 편집 시 훅이 자동 적용한다.
- embedded Qdrant는 단일 프로세스 전용 — 잠금 충돌 시 다른 프로세스를 먼저 종료하고, 재인덱싱은 `artifacts/index*/qdrant` 삭제 후 rebuild.
- 기능 사이클은 `feature/<lane-name>` 브랜치에서 진행하고, 게이트 통과 증거(REPORT.md 갱신)를 포함해 master로 PR한다.

## Decision records (ADR)

- 도구·라이브러리·아키텍처를 채택(또는 의도적 미채택)할 때는 **비교를 선행**하고 `docs/adr/NNNN-<slug>.md`로 남긴다: 선택 기준(가중치), 검증된 비교표, 선택 이유·탈락 사유, 재검토 조건 (템플릿: `docs/adr/TEMPLATE.md`).
- 비교표의 사실은 출처로 검증하고 미검증 항목은 "(미검증)" 표기. 사실상 표준인 trivial 선택은 "기본값 채택 + 한 줄 사유"로 충분.
- trade-off가 비자명한 최종 선택은 단독 결정하지 않고 사용자에게 옵션을 제시한다.

## Agentic hardening

- agent_team_operating_model: ADR-0013을 따른다. 기본은 main integrator 1명이
  작업 분해와 최종 통합을 맡고, disjoint write scope가 명확하면 writer subagent를
  병렬 사용한다. read-only reviewer/explorer도 병렬 사용한다. 활성 subagent는 기본
  2개, 독립 구현 phase에서는 최대 3개까지 허용하며, owner files / forbidden files /
  return contract를 명시한다.
- 병렬화 금지 영역: 같은 파일 동시 수정, `artifacts/` gate evidence 갱신/삭제,
  embedded Qdrant index build/eval, `real_openai`/`pytest -m real`, dependency 또는
  architecture 채택 결정, raw RFP/secret 접근.
- handoff_contract: `/eval-lane`, `eval-gate-analyst`, `langgraph-reviewer`, `portfolio-adversary` handoff는 destination, input payload, input filter, return contract를 명시한 경우에만 실행한다.
- `portfolio-adversary`는 read-only 포트폴리오 비판 전용이다. 반환된 비판은 주 agent가 증거로 검증한 뒤 `accept` / `partial` / `reject`로 분류하고 로드맵에 반영한다.
- guardrail tripwires: destructive artifact 삭제, `real_openai` 비용 실행, external-production 호출, credential 접근, scope broadening은 실행 직전 범위와 증거 파일을 확인한다.
- sensitive_trace_policy: raw model/tool inputs, 원문 RFP, API 응답, 개인정보는 persistent capture 대상에서 제외하고 redaction된 요약과 metrics 근거만 남긴다.
- skill_quality_contract: repo-local skill은 trigger-focused frontmatter, progressive disclosure, lack of surprise, negative/non-trigger 조건을 포함한다.
- memory daemons, telemetry, cloud/API-key 서비스, vector DB, background worker는 storage location, retention, user/project/entity scope가 명시되기 전에는 추가하지 않는다.
