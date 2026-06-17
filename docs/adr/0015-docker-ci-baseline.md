# ADR-0015: Docker and Credential-Free CI Baseline

- 상태: 채택
- 날짜: 2026-06-17
- 결정자: Codex 제안 후 사용자 승인

## 배경

The portfolio now has a FastAPI service surface, but it still needs a repeatable
runtime package and pull-request regression signal. The repository does not
track `data/` or `artifacts/`, and the real lane uses paid `OPENAI_API_KEY`
calls, so the first CI slice must stay credential-free and avoid publishing raw
RFP material in a container image or test fixture.

## 선택 기준

- 높음: GitHub Actions에서 API key 없이 재현 가능한 regression 신호.
- 높음: raw RFP `data/`와 local gate `artifacts/`를 이미지에 굽지 않는 배포 경계.
- 중: FastAPI service를 그대로 실행할 수 있는 production-like entrypoint.
- 중: Python/uv dependency resolution을 local과 CI에서 맞추는 재현성.
- 낮음: 초기 slice에서 cloud deployment까지 한 번에 완성.

## 후보 비교

검증 일자: 2026-06-17. 검증 근거: 현재 저장소의 `.gitignore`, `pyproject.toml`,
`uv.lock`, FastAPI service module, GitHub-hosted runner defaults.

| 기준 | 후보 A: Docker app image + GitHub Actions no-real CI | 후보 B: Docker image with baked data/artifacts | 후보 C: CI real lane with OpenAI secret |
|------|--------|--------|--------|
| credential-free regression | synthetic corpus 후 `pytest -m "not real"`로 가능 | 가능하지만 artifact freshness와 무관 | 불가, secret과 비용 필요 |
| raw corpus boundary | `data/`, `artifacts/` exclude 후 mount | raw corpus와 local artifacts가 image에 포함 | CI runner에는 raw corpus가 없음 |
| portfolio deploy signal | FastAPI `uvicorn` entrypoint 제공 | service + demo data까지 포함 | CI 품질 신호는 강하지만 배포 packaging은 별도 |
| artifact gate fidelity | 로컬 gate evidence 유지, CI는 unit/regression | stale artifact가 image에 굳을 위험 | canonical real gate와 가장 가깝지만 비용/secret 의존 |
| 운영 위험 | 낮음 | 중간: image size, data publication risk | 높음: 비용, quota, secret 관리 |

## 결정

후보 A를 채택한다. Docker image는 FastAPI app과 locked dependency만 포함하고,
`data/`와 `artifacts/`는 런타임 read-only mount 대상으로 둔다. GitHub Actions는
private-data-free synthetic 100-row corpus를 생성한 뒤 `uv sync --frozen --group
dev`, `ruff`, `pytest -m "not real"`을 실행해 PR마다 credential-free regression
신호를 제공한다.

## 탈락 사유

- 후보 B: raw RFP corpus와 local gate artifacts를 이미지에 굽는 방식은 공개/배포
  경계가 불명확하고 stale evidence를 고정할 수 있다.
- 후보 C: 최종 품질 gate에는 필요하지만, 모든 PR CI에 붙이면 비용·quota·secret
  실패가 개발 regression 신호를 오염시킨다.

## 재검토 조건

- 공개 가능한 fixture corpus를 별도로 만들면 CI artifact/report gate job을 추가한다.
- GitHub Actions secret과 비용 예산이 명시되면 nightly 또는 manual real-lane workflow를
  별도로 추가한다.
- cloud 배포 대상이 정해지면 image hardening, non-root user, healthcheck, SBOM을
  deployment ADR에서 재검토한다.

## 출처

- 현재 저장소 파일: `.gitignore`, `pyproject.toml`, `uv.lock`, `rfp_rag/service/app.py`
- GitHub Actions default CI surface: this repository is hosted on GitHub, so
  GitHub Actions is the default CI choice for PR/push checks.
