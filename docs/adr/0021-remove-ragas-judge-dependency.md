# ADR-0021: Ragas 제거와 repo-local LLM judge 전환

- 상태: 채택
- 날짜: 2026-06-19
- 결정자: Codex 제안, security gate fail-closed 근거

## 배경

GitHub Dependabot이 `ragas` `GHSA-95ww-475f-pr4f` low alert를 보고한다.
GitHub API 기준 `first_patched_version=null`이며, 현재 잠금 버전 `0.4.3`도
alert 범위에 포함된다. `diskcache` transitive alert는 ADR-0010에서 제거했지만,
`ragas` 자체 alert는 남는다.

이 레포는 면접용 senior AI Agent Engineer 포트폴리오이므로, 공개 전 dependency
security hygiene가 중요하다. residual risk를 승인하고 dismiss할 수도 있지만,
평가 judge는 public runtime path가 아니라 cost-bearing eval lane에 한정되어 있어
repo-local LLM judge로 대체하는 선택지도 가능하다.

## 선택 기준

| 기준 | 가중치 | 근거 |
|---|---:|---|
| GitHub security alert 제거 | 높음 | 포트폴리오 공개 시 열린 alert는 운영 품질 신호를 깎는다 |
| 기존 평가 파이프라인 보존 | 높음 | `evaluate.py`, `stage3_eval.py`, gate schema를 유지해야 한다 |
| metric 해석 연속성 | 중 | `faithfulness`, `answer_relevancy` 이름은 유지하되 분포 변화 가능성을 기록해야 한다 |
| 변경 범위 | 중 | 새 플랫폼/러너 도입은 CI와 운영 표면을 키운다 |
| 재보정 가능성 | 중 | future real run에서 threshold 재보정 근거를 남길 수 있어야 한다 |

## 후보 비교

| 기준 | A: `ragas` residual risk 수용 | B: `deepeval`로 교체 | C: repo-local LLM judge |
|---|---|---|---|
| security alert | 남음. dismiss/수용 필요 | 제거 가능 | 제거 가능 |
| 기존 pipeline 보존 | 높음 | 중. pytest runner 중심 워크플로와 겹침 | 높음. `single_turn_ascore` shape 유지 |
| metric 연속성 | 가장 높음 | 낮음. metric/threshold 재보정 필요 | 중. 이름과 gate는 유지, scoring rubric은 변경 |
| dependency 표면 | 유지 | 새 dependency 추가 | 감소 |
| 구현 비용 | 낮음 | 중~높음 | 중 |

## 결정

**후보 C: repo-local LLM judge로 전환하고 `ragas` dependency를 제거한다.**

`rfp_rag.judge`는 `langchain-openai`의 `ChatOpenAI`를 그대로 사용하되,
`faithfulness`와 `answer_relevancy`를 repo-local rubric prompt로 채점한다.
`judge_predictions()`의 외부 계약, metric names, warning/fail-fast behavior,
`RFP_JUDGE_MODEL`, `RFP_JUDGE_BASE_URL`, `RFP_JUDGE_API_KEY` override는 유지한다.
`langfuse.langchain.CallbackHandler`가 top-level `langchain` package를 import하므로
`langchain>=1.3.9`는 patched floor로 명시 유지한다.

## 영향과 재보정 조건

- 기존 저장 artifacts의 historical metric 값은 당시 Ragas judge 결과로 해석한다.
- 새 real/open eval run은 repo-local judge rubric으로 생성되므로, major comparison을
  하려면 같은 eval set에서 새 judge 기준으로 재실행해야 한다.
- `faithfulness`와 `answer_relevancy` threshold는 현재 gate 값을 유지하되, 다음
  cost-bearing real run에서 분포가 크게 달라지면 REPORT에 score distribution과
  threshold 변경 근거를 남긴다.
- `ragas`가 patched release를 제공하더라도 기본값은 repo-local judge 유지다. 다시
  채택하려면 ADR-0002를 재개정하고 security alert가 없는 버전을 검증한다.

## 검증

Required local checks:

- `uv lock`
- `uv.lock`에서 `ragas`/`langchain-community`/`diskcache`가 없고
  `langchain>=1.3.9`인지 확인
- `uv run pytest tests/test_judge.py tests/test_production_readiness.py tests/test_portfolio_check.py -q`
- `uv run ruff check .`
- `uv run python -m rfp_rag.production_readiness`
- `uv run python -m rfp_rag.portfolio_check --out artifacts/portfolio_readiness.json`

## 출처

- GitHub Dependabot alert: `ragas` `GHSA-95ww-475f-pr4f`, `first_patched_version=null`
- ADR-0002: prior Ragas judge selection
- ADR-0010: unused Ragas `diskcache` transitive dependency removal
