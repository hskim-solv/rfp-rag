---
name: eval-lane
description: Use when running RFP RAG/agent evaluation lanes, checking gate status (offline_scaffold_complete, rag_quality_complete, agent_lane_complete), rebuilding an index, comparing eval runs, or verifying gates before a PR.
---

# Eval Lane Runbook

## Gate map

| Lane | 비용 | Gate 파일 | Gate 키 |
|------|------|-----------|---------|
| offline RAG | 무료 (키 불필요) | `artifacts/eval/metrics.json` | `offline_scaffold_complete` |
| real RAG | OPENAI_API_KEY, ~$5 | `artifacts/eval_real/metrics.json` | `rag_quality_complete` |
| agent (offline 판정) | 무료 | `artifacts/eval_agent/metrics.json` | `agent_lane_complete` (세부: `gate.failed[]`) |
| real agent smoke | OPENAI_API_KEY, 소액 | — | `pytest -m real` 통과 |

**real lane 명령은 비용이 발생하므로 사용자 명시 요청 없이 실행하지 않는다.**
모든 명령은 repo 루트에서 실행한다. evaluate/evaluate_agent는 `--index` 디렉터리가 먼저 빌드되어 있어야 한다.

## 게이트 일괄 판정

```bash
python3 -c "
import json
for p, k in [('artifacts/eval','offline_scaffold_complete'),
             ('artifacts/eval_real','rag_quality_complete'),
             ('artifacts/eval_agent','agent_lane_complete')]:
    try: print(f'{p}: {k} =', json.load(open(p + '/metrics.json'))[k])
    except FileNotFoundError: print(f'{p}: (run 없음)')
"
```

## Offline lane (회귀 확인 — 키 없이 통과해야 정상)

`rfp_rag/agent/` 를 수정했다면 아래에 더해 Agent lane 판정(다음 섹션, 역시 무료)까지 돌려야 회귀 확인이 완결된다.

```bash
python3 -m pytest -m "not real"
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index --chunk-size 500 --chunk-overlap 80 --embedding-provider offline
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index --out artifacts/eval --provider offline --top-k 5 --min-score 0.15
python3 -m rfp_rag.report_check --eval artifacts/eval --readme README.md
```

## Agent lane (offline 판정)

```bash
python3 -m rfp_rag.agent.evaluate_agent --data data/data_list.csv --files data/files \
  --index artifacts/index --out artifacts/eval_agent --provider offline --top-k 5 --min-score 0.15
```

실패 시 `metrics.json`의 `gate.failed[]`로 미달 메트릭 확인 → `.claude/agents/eval-gate-analyst.md` 서브에이전트로 진단 (Agent/Task 도구에서 `eval-gate-analyst` 타입으로 호출).

## Real lane (사용자 승인 후에만)

```bash
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files \
  --out artifacts/index_real --chunk-size 500 --chunk-overlap 80 --embedding-provider openai
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_real \
  --out artifacts/eval_real --provider real_openai --top-k 5 --min-score 0.47
python3 -m pytest -m real
```

비용 절감: `RFP_JUDGE_MODEL=gpt-5.4-mini` (~$5 → ~$1).

## Run 비교 (회귀 추적)

이전 run을 보존하려면 `--out artifacts/eval_real_runN` 으로 분리 실행 후 메트릭 비교:

```bash
python3 -c "
import json
a = json.load(open('artifacts/eval_real_run1/metrics.json'))['aggregate']
b = json.load(open('artifacts/eval_real/metrics.json'))['aggregate']
[print(f'{k}: {a.get(k)} → {b.get(k)}') for k in sorted(set(a) | set(b))]
"
```

## 주의

- `--min-score` 보정값(offline 0.15 / real 0.47)을 바꾸면 `score_distribution` 근거를 REPORT.md에 기록.
- embedded Qdrant는 단일 프로세스 전용 — 평가 중 다른 프로세스로 같은 인덱스를 열지 않는다.
- artifacts/는 손으로 편집 금지 (게이트 증거).
