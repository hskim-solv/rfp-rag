# ADR-0008: Lane-compatible LLM reranker first

- 상태: 채택
- 날짜: 2026-06-15
- 결정자: 사용자 "그래 그렇게 해" 승인 후 Codex 실행

## 배경

M4 retrieval ablation에서 `vector` gate는 현재 section-aware offline 기준을 통과하지만,
`hybrid` RRF는 후보 확장 효과와 별개로 `abstention_pass=0.2`,
`section_hit_rate=0.7`로 gate 대체가 불가능했다. 다음 단계는 A full deterministic
reranker가 아니라 B real/open reranker다.

단, 새 외부 reranker provider를 바로 채택하면 API key, 비용, latency, 개인정보/trace,
의존성, 평가 범위가 동시에 늘어난다. 먼저 기존 `real_openai` / `open` lane 위에서
동작하는 reranker interface와 artifact schema를 닫고, 실제 비용 실행은 별도 승인 후
수행한다.

## 선택 기준

| 기준 | 가중치 | 근거 |
|------|--------|------|
| 최종 B reranker로 이어지는가 | 높음 | 포트폴리오 목표는 real/open reranker 평가 |
| 새 dependency/API key 최소화 | 높음 | memory daemons/cloud/API-key 서비스 추가는 scope/retention 명시 전 제한 |
| offline lane 불변식 유지 | 높음 | `pytest -m "not real"`은 credential-free여야 함 |
| artifact-backed evaluation | 높음 | `vector`, `hybrid`, `reranked` 비교가 metrics/predictions에 남아야 함 |
| Korean RFP chunk 처리 | 중 | 한국어, 표/섹션/메타데이터 문맥을 다뤄야 함 |
| latency/cost 통제 | 중 | rerank는 후보 수만큼 context를 늘림 |

## 후보 비교

검증일: 2026-06-15.

| 기준 | 기존 lane-compatible LLM reranker | Cohere Rerank API | Jina Reranker API | local CrossEncoder |
|------|------|------|------|------|
| 최종 B 연결 | real/open LLM으로 바로 평가 가능 | 전용 reranker라 강함 | 전용 reranker라 강함, multilingual 강조 | 실제 reranker지만 local infra 성격 |
| 새 dependency/API key | 없음. 기존 LangChain/OpenAI-compatible provider 사용 | 새 SDK 또는 HTTP client, Cohere key 필요 | HTTP client와 Jina key 필요 | `sentence-transformers`/torch/model download 필요 |
| offline lane | default `none` 유지 시 영향 없음 | 별도 paid/API lane 필요 | 별도 paid/API lane 필요 | local dependency가 무거움 |
| artifact schema | 직접 설계 가능 | relevance score 제공 | relevance score 제공 | score/logit 제공 |
| Korean/multilingual | model 선택에 따름 | 한국어 성능은 모델별 확인 필요 | multilingual reranker를 전면 홍보 | 모델 선택에 따라 다름 |
| latency/cost | 후보 chunk를 LLM context로 보냄. 비용 발생 | API request per query | API request per query | CPU/GPU latency와 model cache 필요 |
| 이번 단계 적합성 | 가장 적합. B interface를 먼저 닫음 | 다음 provider ADR 후보 | 다음 provider ADR 후보 | local reranker ADR 후보 |

## 결정

**기존 lane-compatible LLM reranker를 1차 채택한다.**

구현 범위는 `--reranker none|llm`과 `--rerank-candidate-k`를 추가하고,
`none`을 기본값으로 유지한다. `llm`은 `real_openai` 또는 `open` provider에서만 허용한다.
offline lane은 credential-free contract이므로 LLM reranker를 실행하지 않는다.

A deterministic full reranker는 구현하지 않는다. 기존 `vector`와 `hybrid`가 control이며,
필요한 것은 또 하나의 offline search engine이 아니라 B reranker를 평가할 인터페이스,
메트릭, artifact다.

## 탈락 사유

- Cohere Rerank API: 전용 reranker로 유력하지만 새 API key와 provider ADR이 필요하다.
- Jina Reranker API: multilingual/API 후보로 유력하지만 새 API key와 provider ADR이 필요하다.
- local CrossEncoder: privacy와 local 재현성은 좋지만 dependency/model download/GPU-CPU
  latency 관리가 먼저 필요하다.

## 재검토 조건

- LLM reranker가 `abstention_pass` 또는 `section_hit_rate`를 개선하지 못할 때
- LLM reranker 비용/latency가 real lane judge 비용보다 커질 때
- 한국어 RFP에서 dedicated reranker가 명확히 더 좋은 품질/비용을 보일 때
- dashboard/service 단계에서 reranker score explainability가 더 필요해질 때

## 출처

- OpenAI Structured Outputs: https://platform.openai.com/docs/guides/structured-outputs
- Cohere Rerank API: https://docs.cohere.com/reference/rerank
- Jina Reranker API: https://jina.ai/reranker/
- Sentence Transformers CrossEncoder usage:
  https://sbert.net/docs/cross_encoder/usage/usage.html
- Repo evidence: `artifacts/eval/metrics.json`,
  `artifacts/eval_hybrid_offline/metrics.json`, `REPORT.md` §15
