# ADR-0005: open lane 백엔드 선정과 judge 모델 전략

- 상태: 채택
- 날짜: 2026-06-11
- 결정자: 사용자 (Claude 비교 제시 후 "mini + open lane 둘 다" 승인)

## 배경

real lane 풀 사이클 비용은 ~$5(judge 지배적)로, 품질 실험(hybrid/BM25 등)을
반복하기엔 비싸다. 남은 로드맵 분석 결과 judge 풀 런은 0~1회 수준이지만,
품질 이터레이션을 시작하는 순간 반복 비용이 문제가 된다. 이에 따라:

1. **judge 기본 모델**을 gpt-5.4 → gpt-5.4-mini로 전환해 상시 비용을 줄이고,
2. **open lane**(오픈소스/저가 모델 기반 저비용 이터레이션 레인)을 추가한다.

open lane은 게이트 증거가 아니라 이터레이션 신호 전용이다 — `decide_gates`는
`lane != "real_openai"`에서 `rag_quality_complete`를 주장하지 않는다
(contract: `rfp-rag-open-v1`).

## 선택 기준

| 기준 | 가중치 | 이유 |
|------|--------|------|
| 60건 풀 평가 실행 가능성 (rate limit) | 높음 | 평가셋 60건 + judge 재시도를 한 번에 돌 수 있어야 함 |
| 비용/런 | 높음 | 이터레이션 레인의 존재 이유 |
| OpenAI 호환 API (base_url 오버라이드) | 높음 | `ChatOpenAI(base_url=...)` 하나로 구현 — lane 코드 추가 최소화 |
| structured output (tool calls) | 높음 | `LLMAnswer` 스키마 추출이 생성 경로의 전제 |
| 라이선스 (포트폴리오 공개 적합성) | 중 | NC 라이선스는 간접 수익화 금지로 회색지대 |
| 로컬 폴백 | 중 | 원격 백엔드 장애/잔액 소진 시 대체 경로 |

## 후보 비교 — 생성 백엔드 (검증일 2026-06-11)

| 기준 | DeepSeek API | Ollama 로컬 (Qwen3 8B) | OpenRouter free | Groq free | Colab |
|------|--------------|------------------------|-----------------|-----------|-------|
| 60건 풀 런 | ✓ 제한 없음 수준 | ✓ (단 30분~1시간, 미실측) | ✗ 50 req/일 한도 | △ TPM 6K 병목 | △ 세션 휘발 |
| 비용/런 (생성만) | ~$0.05 | $0 (전기료 제외) | $0 | $0 | $0 |
| OpenAI 호환 | ✓ `api.deepseek.com` | ✓ `localhost:11434/v1` | ✓ | ✓ | ✗ 노트북 기반 |
| tool calls | ✓ | ✓ (Qwen3) | 모델별 상이 | 모델별 상이 | (해당 없음) |
| 가격 | $0.14/M in(캐시미스), $0.28/M out | — | — | — | — |
| 비고 | 1M 컨텍스트, 중국 서버 전송 | M2 Air 16GB에서 Q4 ~5GB 구동 가능 | 풀 런 불가가 결정적 | 재시도 포함 시 병목 | CLI 파이프라인 부적합 |

코퍼스는 공개 입찰 RFP라 중국 서버 전송의 민감도는 낮다고 판단.

## 후보 비교 — 로컬 모델 라이선스 (검증일 2026-06-11)

| 모델 | 라이선스 | 포트폴리오 공개 |
|------|----------|----------------|
| Qwen3 (전 모델) | Apache 2.0 | ✓ |
| EXAONE 3.5/4.0 | NC (비상업 연구·교육 전용) | ✗ 간접 수익화(채용 어필) 회색지대 |
| DeepSeek V4 오픈웨이트 | MIT | ✓ (단 로컬 구동엔 너무 큼 — API 사용) |

임베딩: DeepSeek은 임베딩 API가 없어 분리 필요 → **bge-m3** (Ollama 공식,
1.2GB, 다국어/한국어 지원)를 로컬 기본으로 선정.

## 결정

- **생성**: DeepSeek `deepseek-v4-flash` 기본 (`RFP_OPEN_BASE_URL`/`RFP_OPEN_MODEL`로
  오버라이드), Ollama Qwen3 8B를 로컬 백업으로 지원 (base_url만 교체).
- **임베딩**: Ollama `bge-m3` 기본 (`RFP_OPEN_EMBEDDING_*`).
- **judge 3단 전략**:
  1. 최종 게이트(real lane): `gpt-5.4-mini` 기본값 — §10-11 A/B에서 gpt-5.4 대비
     게이트 판정 일치, 점수 이탈은 보수적 방향, 비용 1/6 ($0.32/60건) 검증.
  2. 이터레이션(open lane): DeepSeek judge — `RFP_JUDGE_BASE_URL` 오버라이드로
     지원. 채택 전 A/B 검증 필요 (2026-06-11 기준 DeepSeek 잔액 402로 보류).
  3. self-judging 편향 회피: 최종 심판은 생성 모델과 다른 계열을 유지한다
     (open lane 생성이 DeepSeek이면 최종 judge는 OpenAI).

## 탈락 사유

- OpenRouter free: 50 req/일 — 60건 평가 + judge 재시도 불가.
- Groq free: TPM 6K — 긴 컨텍스트(chunk 5개) 평가에서 병목.
- Colab: 노트북 기반 세션 휘발 — CLI 파이프라인(`build_index`/`evaluate`)과 부적합.
- EXAONE: NC 라이선스 — 포트폴리오 공개 목적과 충돌.
- RunPod 등 GPU 대여: 8B급 모델엔 API 단가가 우월.

## 재검토 조건

- `deepseek-chat` 별칭 폐기(2026-07-24 예고) 이후 모델명 정책 변화.
- DeepSeek 가격 인상 또는 OpenRouter free 한도 완화 (풀 런 가능 수준).
- open lane에서 hybrid/BM25 실험이 본격화되어 judge 반복 횟수가 주당 5회를
  넘는 경우 — DeepSeek judge A/B를 우선 완료할 것.
- M2 로컬 Qwen3 8B 실측에서 60건 평가가 1시간을 초과하면 로컬 백업 의미 재평가.

## 출처

- DeepSeek 가격/모델: https://api-docs.deepseek.com/quick_start/pricing (2026-06-11 확인)
- Qwen3 라이선스: https://huggingface.co/Qwen/Qwen3-8B (Apache 2.0)
- EXAONE 라이선스: https://huggingface.co/LGAI-EXAONE (NC 조항)
- OpenRouter free 한도: https://openrouter.ai/docs/api-reference/limits
- bge-m3 Ollama: https://ollama.com/library/bge-m3
- mini judge A/B: REPORT.md §10-11 (artifacts/judge_ab/summary.json)
