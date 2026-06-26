# ADR-0024: localhost.run tunnel for current hosted reviewer evidence

- 상태: 채택
- 날짜: 2026-06-25
- 결정자: Codex 제안 후 사용자 외부 배포 승인

## 배경

목표는 비용 없는 public-safe HTTPS reviewer demo evidence를 생성하는 것이다.
Render dashboard 조작은 Chrome/Computer Use 타임아웃으로 실행할 수 없었고, Render
API/CLI token도 없었다. Hugging Face MCP connector는 인증되어 있었지만 로컬 HF CLI
token이 없고 HF Jobs는 pre-paid credit 부족으로 Space 생성 경로가 막혔다.

인증 없는 `localhost.run` SSH reverse tunnel은 현재 로컬 public-demo FastAPI service를
외부 HTTPS URL로 노출할 수 있고, reviewer-token/rate-limit/source-boundary smoke를
실제 HTTPS 경로에서 검증할 수 있다.

## 선택 기준

- 높음: 현재 세션에서 실제 HTTPS URL을 만들 수 있을 것.
- 높음: 비용과 API token 없이 동작할 것.
- 높음: public-safe demo profile만 노출하고 reviewer-token/rate-limit 경계를 유지할 것.
- 중: evidence artifact에 provider 한계를 정직하게 남길 것.
- 중: full production/SLO/always-on claim으로 오해되지 않을 것.

## 후보 비교

검증일: 2026-06-25.

| 기준 | Render Blueprint | Hugging Face Docker Space | localhost.run tunnel |
|------|------------------|---------------------------|----------------------|
| 현재 실행 가능성 | Chrome UI 타임아웃, API token 없음 | local token 없음, Jobs credit 부족 | SSH reverse tunnel 생성 성공 |
| HTTPS URL | 가능하나 미생성 | 가능하나 미생성 | `*.lhr.life` URL 생성 |
| 비용 | free plan 가능 | free Space 가능 | 무료 anonymous tunnel |
| secret/env | dashboard/API 필요 | Space secret API 필요 | 로컬 env로 reviewer token 주입 |
| evidence 강도 | 가장 강함 | 강함 | reviewer demo tunnel evidence, always-on 아님 |
| production 오해 위험 | 중 | 낮음 | 낮음, tunnel non-claim 명시 필요 |

## 결정

현재 세션의 hosted reviewer evidence provider로 `localhost.run` tunnel을 채택한다.
이는 full hosted production이나 always-on SaaS가 아니라, public-safe reviewer demo를
외부 HTTPS 경로에서 검증하기 위한 제한된 evidence source다.

## 탈락 사유

- Render Blueprint: 현재 자동화 가능한 인증/브라우저 제어 경로가 없다.
- Hugging Face Docker Space: local HF token이 없고 Jobs credit 부족으로 생성할 수 없다.

## 재검토 조건

- Render API key, 안정적인 Chrome dashboard control, 또는 HF token이 제공된다.
- reviewer demo가 며칠 이상 유지되어야 하거나 외부 면접관이 비동기 접근해야 한다.
- tunnel provider가 rate-limit, uptime, TLS, logging 요구를 만족하지 못한다.

## 출처

- localhost.run tunnel output generated in this session.
- Render CLI/auth absence verified locally.
- Hugging Face local CLI auth absence and Jobs 402 credit failure verified locally.
