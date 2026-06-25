# ADR-0023: Hugging Face Space hosted reviewer demo fallback

- 상태: 채택
- 날짜: 2026-06-25
- 결정자: Codex 제안 후 사용자 외부 배포 승인

## 배경

ADR-0022는 public-safe hosted reviewer demo의 기본 배포 후보로 Render
Blueprint를 선택했다. 실제 실행 시점에 Render CLI/API 인증이 없고 Chrome UI
제어도 현재 세션에서 안정적으로 동작하지 않았다. 반면 Hugging Face 계정은
`hskim-solv`로 인증되어 있고, `hf repo create --repo-type space --space_sdk docker`
및 `huggingface_hub`의 Space secret/variable API를 사용할 수 있다.

목표는 full hosted production SaaS가 아니라, 비용 없는 public-safe HTTPS reviewer
demo URL과 smoke/evidence artifact를 확보하는 것이다.

## 선택 기준

- 높음: 비용 없는 HTTPS hosted URL을 실제로 생성할 수 있을 것.
- 높음: Docker 기반 FastAPI service를 그대로 실행할 수 있을 것.
- 높음: reviewer token secret과 public demo env를 provider 환경변수로 설정할 수 있을 것.
- 중: CI/local reviewer workflow와 artifact evidence가 기존 gate에 자연스럽게 연결될 것.
- 중: full production/SLO claim으로 오해되지 않도록 non-claim 경계가 명확할 것.

## 후보 비교

검증일: 2026-06-25.

| 기준 | Render Blueprint | Hugging Face Docker Space |
|------|------------------|---------------------------|
| 현재 세션 인증 | `render` CLI/API key 없음, Chrome UI 제어 타임아웃 | `hf` CLI 사용 가능, `hskim-solv` 인증 확인 |
| 무료 HTTPS URL | Free web service 가능 | Free CPU Space HTTPS URL 가능 |
| Docker FastAPI 실행 | `render.yaml` + Dockerfile 가능 | Docker Space + `app_port` metadata 가능 |
| secret/env 설정 | Dashboard/Blueprint secret 필요 | `huggingface_hub` `add_space_secret` / `add_space_variable` 사용 가능 |
| evidence 연결 | 기존 ADR-0022와 runbook에 이미 문서화 | provider 옵션과 deploy script 추가 필요 |
| production 오해 위험 | 낮음, Render web service 용어는 production처럼 보일 수 있음 | 낮음, Space는 demo surface로 설명하기 쉬움 |

## 결정

Hugging Face Docker Space를 현재 실행 가능한 hosted reviewer demo provider로 채택한다.
Render Blueprint는 ADR-0022의 기본 provider 후보로 유지하되, 인증/운영 조건이 준비될
때까지 HF Space를 비용 없는 public-safe HTTPS reviewer demo evidence source로 사용한다.

## 탈락 사유

- Render Blueprint: 현재 세션에 Render CLI/API key가 없고, Chrome UI 조작 도구가
  타임아웃되어 실제 배포를 완료할 수 없다.

## 재검토 조건

- Render API key 또는 안정적인 dashboard automation이 제공된다.
- Hugging Face Free Space 정책이 바뀌거나 Docker Space가 `/healthz` uptime/sleep
  요구를 만족하지 못한다.
- reviewer demo가 full SaaS production claim으로 확대되어 managed web service,
  custom domain, SLO, billing telemetry가 필요해진다.

## 출처

- Hugging Face Docker Spaces: https://huggingface.co/docs/hub/spaces-sdks-docker
- Hugging Face Spaces secrets and variables: https://huggingface.co/docs/hub/spaces-overview#managing-secrets
- Hugging Face Hub CLI: https://huggingface.co/docs/huggingface_hub/guides/cli
- Hugging Face Hub API `create_repo`, `add_space_secret`, `add_space_variable` verified from installed `huggingface_hub==1.16.1`.
