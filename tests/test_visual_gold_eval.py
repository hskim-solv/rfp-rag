from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.visual_gold_eval import (
    check_visual_candidate_summary,
    evaluate_visual_gold_candidates,
    run_visual_gold_eval,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _gold_facts() -> list[dict]:
    return [
        {
            "record_id": "doc:001:p3:gantt_schedule",
            "fact_type": "visual_type_present",
            "field": "schedule",
            "value": "Gantt schedule is present",
            "reviewer": "reviewer_a",
            "status": "accepted",
        },
        {
            "record_id": "doc:002:p5:system_architecture_diagram",
            "fact_type": "visual_type_present",
            "field": "system_architecture",
            "value": "System diagram is present",
            "reviewer": "reviewer_a",
            "status": "accepted",
        },
        {
            "record_id": "doc:003:p1:gantt_schedule",
            "fact_type": "visual_type_present",
            "field": "schedule",
            "value": "Candidate schedule claim not supported",
            "reviewer": "reviewer_a",
            "status": "rejected",
        },
    ]


def test_evaluate_visual_gold_candidates_scores_precision_recall_and_negatives() -> (
    None
):
    candidates = [
        {
            "record_id": "doc:001:p3:gantt_schedule",
            "fact_type": "visual_type_present",
            "field": "schedule",
            "value": "Gantt schedule detected",
        },
        {
            "record_id": "doc:003:p1:gantt_schedule",
            "fact_type": "visual_type_present",
            "field": "schedule",
            "value": "Gantt schedule detected",
        },
        {
            "record_id": "doc:999:p1:gantt_schedule",
            "fact_type": "visual_type_present",
            "field": "schedule",
            "value": "Unknown candidate",
        },
    ]

    result = evaluate_visual_gold_candidates(_gold_facts(), candidates)

    assert result["decision"] == "visual_gold_candidate_eval"
    assert result["positive_gold_count"] == 2
    assert result["negative_gold_count"] == 1
    assert result["candidate_fact_count"] == 3
    assert result["true_positive_count"] == 1
    assert result["false_positive_count"] == 2
    assert result["false_negative_count"] == 1
    assert result["negative_violation_count"] == 1
    assert result["unknown_candidate_count"] == 1
    assert result["precision"] == 0.33333333
    assert result["recall"] == 0.5
    assert result["f1"] == 0.4


def test_run_visual_gold_eval_writes_summary(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.jsonl"
    candidate_path = tmp_path / "candidate.jsonl"
    out_dir = tmp_path / "eval"
    _write_jsonl(gold_path, _gold_facts())
    _write_jsonl(
        candidate_path,
        [
            {
                "record_id": "doc:001:p3:gantt_schedule",
                "fact_type": "visual_type_present",
                "field": "schedule",
                "value": "Gantt schedule detected",
            }
        ],
    )

    result = run_visual_gold_eval(gold_path, candidate_path, out_dir)

    assert result["precision"] == 1.0
    assert result["recall"] == 0.5
    saved = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert saved["false_negative_count"] == 1


def test_run_visual_gold_eval_cli_prints_summary(tmp_path: Path, capsys) -> None:
    from rfp_rag.run_visual_gold_eval import main

    gold_path = tmp_path / "gold.jsonl"
    candidate_path = tmp_path / "candidate.jsonl"
    out_dir = tmp_path / "eval"
    _write_jsonl(gold_path, _gold_facts())
    _write_jsonl(candidate_path, [])

    assert (
        main(
            [
                "--gold",
                str(gold_path),
                "--candidate",
                str(candidate_path),
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["candidate_fact_count"] == 0
    assert payload["recall"] == 0.0


def test_check_visual_candidate_summary_passes_when_targets_are_met() -> None:
    result = check_visual_candidate_summary(
        {
            "precision": 0.76923077,
            "recall": 0.8,
            "f1": 0.78431373,
            "negative_violation_count": 3,
            "candidate_fact_count": 26,
            "true_positive_count": 20,
        }
    )

    assert result["decision"] == "visual_candidate_gate"
    assert result["ok"] is True
    assert result["failures"] == []
    assert result["metrics"]["precision"] == 0.76923077
    assert result["thresholds"]["min_recall"] == 0.7


def test_check_visual_candidate_summary_fails_below_targets() -> None:
    result = check_visual_candidate_summary(
        {
            "precision": 0.69,
            "recall": 0.8,
            "f1": 0.69,
            "negative_violation_count": 4,
            "candidate_fact_count": 26,
            "true_positive_count": 20,
        }
    )

    assert result["ok"] is False
    assert {
        "metric": "precision",
        "actual": 0.69,
        "threshold": 0.7,
        "comparator": ">=",
    } in result["failures"]
    assert {
        "metric": "negative_violation_count",
        "actual": 4,
        "threshold": 3,
        "comparator": "<=",
    } in result["failures"]


def test_run_visual_candidate_check_cli_exits_nonzero_for_failed_summary(
    tmp_path: Path, capsys
) -> None:
    from rfp_rag.run_visual_candidate_check import main

    summary_path = tmp_path / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "precision": 0.69,
                "recall": 0.8,
                "f1": 0.69,
                "negative_violation_count": 4,
                "candidate_fact_count": 26,
                "true_positive_count": 20,
            }
        ),
        encoding="utf-8",
    )

    assert main(["--summary", str(summary_path)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["failures"][0]["metric"] == "precision"


def test_run_visual_candidate_check_cli_writes_gate_artifact(
    tmp_path: Path, capsys
) -> None:
    from rfp_rag.run_visual_candidate_check import main

    summary_path = tmp_path / "summary.json"
    out_dir = tmp_path / "gate"
    summary_path.write_text(
        json.dumps(
            {
                "precision": 0.8,
                "recall": 0.8,
                "f1": 0.8,
                "negative_violation_count": 3,
                "candidate_fact_count": 26,
                "true_positive_count": 20,
            }
        ),
        encoding="utf-8",
    )

    assert main(["--summary", str(summary_path), "--out", str(out_dir)]) == 0
    payload = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert saved["decision"] == "visual_candidate_gate"
    assert saved["ok"] is True
