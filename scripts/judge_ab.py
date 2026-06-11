"""저장된 predictions.jsonl에 현재 RFP_JUDGE_MODEL로 judge만 재실행해 A/B 비교한다.

생성(generation)을 재실행하지 않으므로 judge 모델 차이만 분리해 측정한다.
원본 아티팩트는 읽기만 하고, 결과는 --out 디렉터리에 쓴다 (게이트 증거 불변).

사용:
  set -a; source .env; set +a
  RFP_JUDGE_MODEL=gpt-5.4-mini python3 scripts/judge_ab.py \
    --predictions artifacts/eval_real/predictions.jsonl --out artifacts/judge_ab
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from rfp_rag.judge import judge_predictions
from rfp_rag.tracing import flush_tracing

METRICS = ("faithfulness", "answer_relevancy")


def _mean(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    records = [
        json.loads(line)
        for line in args.predictions.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    baseline = [record.pop("judge", None) for record in records]
    rejudged = judge_predictions(records)
    flush_tracing()

    rows = []
    for old, new in zip(baseline, rejudged):
        rows.append(
            {
                "query_id": new["query_id"],
                "query_type": new["query_type"],
                "baseline": {m: (old or {}).get(m) for m in METRICS},
                "rejudged": {m: new["judge"].get(m) for m in METRICS},
            }
        )

    def _deltas(metric: str) -> list[float | None]:
        return [
            abs(r["rejudged"][metric] - r["baseline"][metric])
            if r["rejudged"][metric] is not None and r["baseline"][metric] is not None
            else None
            for r in rows
        ]

    summary = {
        "judge_model": os.environ.get("RFP_JUDGE_MODEL", "gpt-5.4"),
        "n_predictions": len(rows),
        "baseline_mean": {m: _mean([r["baseline"][m] for r in rows]) for m in METRICS},
        "rejudged_mean": {m: _mean([r["rejudged"][m] for r in rows]) for m in METRICS},
        "mean_abs_delta": {m: _mean(_deltas(m)) for m in METRICS},
        "max_abs_delta": {
            m: max((d for d in _deltas(m) if d is not None), default=None)
            for m in METRICS
        },
        "rejudged_warnings": sorted(
            {w for p in rejudged for w in p["judge"].get("warnings", [])}
        ),
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "judge_ab.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    (args.out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
