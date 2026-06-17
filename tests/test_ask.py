from __future__ import annotations

from pathlib import Path
from typing import Any

from rfp_rag import ask


def test_ask_main_passes_visual_sidecar_paths(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    seen: dict[str, Any] = {}

    def fake_answer_query(*args: Any, **kwargs: Any) -> dict[str, Any]:
        seen["args"] = args
        seen["kwargs"] = kwargs
        return {"answer": "ok"}

    monkeypatch.setattr(ask, "answer_query", fake_answer_query)

    rc = ask.main(
        [
            "--index",
            str(tmp_path / "idx"),
            "--query",
            "질문",
            "--visual-candidates",
            str(tmp_path / "candidate_facts.jsonl"),
            "--visual-gate",
            str(tmp_path / "gate" / "summary.json"),
        ]
    )

    assert rc == 0
    assert '"answer": "ok"' in capsys.readouterr().out
    assert seen["kwargs"]["visual_candidate_path"] == tmp_path / "candidate_facts.jsonl"
    assert seen["kwargs"]["visual_gate_path"] == tmp_path / "gate" / "summary.json"
