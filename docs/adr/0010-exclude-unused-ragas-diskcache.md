# ADR-0010: 사용하지 않는 Ragas diskcache dependency 제외

- 상태: 대체됨 (ADR-0021에서 Ragas 자체 제거)
- 날짜: 2026-06-16
- 결정자: 사용자 "이렇게 가자" 승인

## 배경

GitHub Dependabot이 `uv.lock`에서 `diskcache` medium alert와 `ragas` low alert를
보고했다. `diskcache`는 프로젝트 코드에서 직접 쓰지 않고, `ragas`가 끌고 오는
transitive dependency다.

조사 결과 Ragas의 cache 문서는 `DiskCacheBackend`를 별도 backend로 설명하고,
`diskcache` import도 `DiskCacheBackend` 생성 시점에만 발생한다. 이 프로젝트의
judge lane은 `ragas.cache.DiskCacheBackend`를 사용하지 않는다. 반면 Ragas
`pyproject.toml`은 `diskcache>=5.6.3`를 core dependency로 선언하고 있어 lockfile에
포함된다.

## 선택 기준

| 기준 | 가중치 | 근거 |
|------|--------|------|
| judge 평가 연속성 | 높음 | 기존 real/open lane의 Ragas metric 해석을 유지해야 함 |
| 미사용 vulnerable dependency 제거 | 높음 | 포트폴리오/운영 품질상 unused alert를 남기지 않는 편이 낫다 |
| offline lane credential-free 유지 | 높음 | dependency 변경 후에도 `pytest -m "not real"`이 key 없이 통과해야 함 |
| 변경 범위 최소화 | 중 | evaluator migration은 threshold 재보정과 real lane 재검증 비용이 큼 |
| 재검토 가능성 | 중 | Ragas upstream packaging 또는 patched release가 바뀔 수 있음 |

## 후보 비교

검증일: 2026-06-16.

| 기준 | 후보 A: 현 상태 유지 | 후보 B: `uv exclude-dependencies = ["diskcache"]` | 후보 C: Ragas 제거/대체 |
|------|------|------|------|
| judge 평가 연속성 | 유지 | 유지 | 깨짐. metric/threshold 재보정 필요 |
| diskcache alert | 남음 | lockfile에서 제거 가능 | 제거 가능 |
| 변경 범위 | 없음 | 작음. resolver 설정과 lockfile만 변경 | 큼. judge implementation 교체 |
| offline lane | 유지 | 검증 필요 | 검증/재보정 필요 |
| 설명 가능성 | "패치 없음" 방어만 가능 | "사용하지 않는 optional-like backend 제거"로 설명 가능 | 강하지만 비용이 큼 |

## 결정

**후보 B: `uv`의 `exclude-dependencies`로 `diskcache`를 제외한다.**

`pyproject.toml`에 다음 설정을 추가한다.

```toml
[tool.uv]
exclude-dependencies = ["diskcache"]
```

`uv lock` 결과:

- `uv.lock` manifest에 `excludes = ["diskcache"]` 기록
- `diskcache` package block 제거
- `ragas` dependency list에서 `diskcache` edge 제거

## 검증 결과

```bash
uv sync
```

Result:

```text
Uninstalled diskcache==5.6.3
```

```bash
OPENAI_API_KEY=dummy uv run python - <<'PY'
import importlib.util
print(importlib.util.find_spec("diskcache"))
from rfp_rag.judge import _build_metrics
print(sorted(_build_metrics()))
PY
```

Result:

```text
None
['answer_relevancy', 'faithfulness']
```

```bash
uv run python -m pytest tests/test_judge.py tests/test_gates.py tests/test_reaggregate.py -q
```

Result: `32 passed`.

```bash
env -u OPENAI_API_KEY -u LANGFUSE_PUBLIC_KEY -u LANGFUSE_SECRET_KEY \
  uv run python -m pytest -p no:cacheprovider -m "not real" --tb=short -q
```

Result: `250 passed, 5 deselected`.

## 탈락 사유

- 후보 A: 현재 latest package에 patched version이 없다는 설명은 가능하지만,
  미사용 dependency alert가 계속 남아 portfolio/security hygiene 관점에서 약하다.
- 후보 C: `ragas` 자체 alert까지 제거할 가능성은 있지만, real/open lane judge metric과
  threshold를 다시 세워야 한다. 현재 문제는 `diskcache` 미사용 dependency 제거만으로
  더 작게 줄일 수 있다.

## 재검토 조건

- Ragas가 `diskcache`를 optional dependency로 옮기거나 core dependency에서 제거할 때
- Ragas judge path가 `DiskCacheBackend` 없이 동작하지 않게 바뀔 때
- GitHub Dependabot이 `ragas` 자체 alert를 계속 유지하고 portfolio 공개 전 보안
  노이즈를 제거해야 할 때
- `deepeval` 또는 자체 judge migration을 별도 ADR에서 채택할 때

## 출처

- https://docs.ragas.io/en/latest/references/cache/
- https://docs.ragas.io/en/stable/howtos/customizations/_caching/
- https://github.com/explodinggradients/ragas/blob/main/pyproject.toml
- https://docs.astral.sh/uv/reference/settings/#exclude-dependencies
