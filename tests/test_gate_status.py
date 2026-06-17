from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.gate_status import collect_gate_status, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_collect_gate_status_reads_all_lane_artifacts(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "artifacts/eval/metrics.json",
        {"offline_scaffold_complete": True, "provider_lane": "offline"},
    )
    _write_json(
        tmp_path / "artifacts/eval_real/metrics.json",
        {"rag_quality_complete": True, "provider_lane": "real_openai"},
    )
    _write_json(
        tmp_path / "artifacts/eval_agent/metrics.json",
        {
            "agent_lane_complete": True,
            "gate": {"failed": []},
        },
    )
    _write_json(
        tmp_path / "artifacts/visual_tesseract_candidate_expanded_gate/summary.json",
        {"ok": True, "decision": "visual_candidate_gate"},
    )

    status = collect_gate_status(tmp_path)

    assert status["overall_ok"] is True
    assert status["lanes"]["offline_rag"]["value"] is True
    assert status["lanes"]["real_rag"]["value"] is True
    assert status["lanes"]["agent_offline"]["failed"] == []
    assert status["lanes"]["visual_candidate"]["path"] == (
        "artifacts/visual_tesseract_candidate_expanded_gate/summary.json"
    )


def test_collect_gate_status_reports_missing_without_raising(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "artifacts/eval/metrics.json",
        {"offline_scaffold_complete": True},
    )

    status = collect_gate_status(tmp_path)

    assert status["overall_ok"] is False
    assert status["lanes"]["offline_rag"]["present"] is True
    assert status["lanes"]["real_rag"] == {
        "gate_key": "rag_quality_complete",
        "ok": False,
        "path": "artifacts/eval_real/metrics.json",
        "present": False,
        "value": None,
    }


def test_gate_status_main_prints_json(capsys, tmp_path: Path) -> None:
    _write_json(
        tmp_path / "artifacts/eval/metrics.json",
        {"offline_scaffold_complete": True},
    )

    rc = main(["--root", str(tmp_path)])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["lanes"]["offline_rag"]["ok"] is True
    assert payload["lanes"]["agent_offline"]["present"] is False
