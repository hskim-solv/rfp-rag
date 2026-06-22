# 한국어 1-page Case Study: RFP Agentic RAG

## 한 줄 요약

한국 공공입찰 RFP 100건의 HWP/PDF 원문을 source of truth로 삼아, 검색(retrieval),
근거 인용(citation), LangGraph 에이전트(agent) 워크플로우, FastAPI/SSE 서비스,
평가(evaluation), 관찰성(observability), 보안(guardrails)을 gate로 검증하는
production-adjacent Agentic RAG backend입니다.

## 왜 시니어 AI Agent Engineer 포트폴리오인가

이 프로젝트의 핵심은 “답변 하나를 잘 생성했다”가 아니라, 실제 업무형 문서 시스템을
측정 가능하고 방어 가능한 backend로 만든 것입니다. CSV는 metadata registry로만
사용하고, RAG 본문은 원본 HWP/PDF 파싱 산출물에서 가져옵니다. 답변은 chunk/document
lineage와 citation을 가져야 하며, stale artifact나 contract mismatch는 `gate_status`와
`portfolio_check`에서 fail-closed됩니다.

## 구현된 증거

| 영역 | 증거 |
|---|---|
| RAG 품질 | real lane 및 Stage 3 holdout: `recall@5=1.0`, `mrr=1.0`, `citation_validity=1.0`, `faithfulness=0.9887`, `answer_relevancy=0.8797` |
| Agent orchestration | LangGraph route/retrieve/grade/rewrite/generate/verify/HITL, checkpoint, audit redaction, planner-executor scenario evidence |
| Backend/service | FastAPI/Pydantic, async endpoint, SSE streaming, `/healthz`, `/v1/answer`, `/v1/answer/stream`, `/v1/gates`, `/v1/ops/summary` |
| Evaluation | offline/real/agent/visual/security/cost gates, Stage 2/Stage 3 artifact contracts, credential-free regression tests |
| Observability | redacted local trace export, latency p50/p95, token/cost estimate, tool success/failure, failed-run analysis 5건 |
| Guardrails/security | prompt injection, malicious evidence/tool output, secrets/PII leakage, publishable allowlist, dependency alert 0 |
| 운영 경계 | Docker/CI/local reviewer demo는 검증됨. hosted production, public dashboard, live SLO는 아직 claim하지 않음 |
| Tool contract | `docs/portfolio/tool-contract-matrix.md`에 schema, side-effect class, auth/rate-limit boundary, timeout/output cap, redaction, audit/error fields를 기록 |

## 중요한 설계 판단

- **Vector retrieval 유지:** BM25/hybrid/reranker를 유행 때문에 채택하지 않고,
  같은 frozen set에서 품질/비용/latency/citation/abstention을 이겨야만 claim합니다.
- **Ragas 제거:** transitive dependency 보안 alert가 public portfolio 신뢰도를 깎기
  때문에 repo-local judge로 이전하고 dependency security gate를 닫았습니다.
- **Production-adjacent wording:** hosted service처럼 과장하지 않고,
  local/container에서 재현 가능한 운영형 증거를 포트폴리오 claim으로 둡니다.
- **Planner-executor 표현 제한:** 현재 강한 증거는 typed LangGraph workflow와
  planner-executor scenario evidence입니다. 동적 planner runtime이나 supervisor-worker
  production agent라고 말하지 않습니다.

## 면접에서 보여줄 순서

1. `docs/portfolio/reviewer-evidence-map.md`로 10분 검토 경로를 보여줍니다.
2. `docs/architecture/system-architecture.md`로 parsing -> retrieval -> agent/service -> gates 흐름을 설명합니다.
3. `python3 -m rfp_rag.gate_status`와 `artifacts/portfolio_readiness.json`으로 stale evidence가 fail-closed됨을 보여줍니다.
4. Stage 3 holdout, LangGraph agent stress, observability, security artifacts를 순서대로 보여줍니다.
5. 마지막에 non-claim을 명확히 말합니다: hosted cloud production, public dashboard, provider billing telemetry, live-traffic SLO, reranker quality win은 아직 별도 승인/증거가 필요합니다.

## 현재 한계와 다음 단계

현재 레포는 시니어 포트폴리오용 local/container evidence bundle로는 강합니다. 다음
상위 보강은 public reviewer URL 또는 녹화 demo video, 실제 trace dashboard export,
provider billing telemetry, hosted auth/rate-limit/SLO 증거입니다. 이들은 비용, credential,
public disclosure가 걸리므로 사용자 승인 후 별도 phase로 진행해야 합니다.
