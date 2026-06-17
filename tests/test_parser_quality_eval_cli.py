from __future__ import annotations

import json
from pathlib import Path

from rfp_rag import run_parser_quality_eval as cli_module
from rfp_rag.run_parser_quality_eval import main, run_parser_quality_eval


def test_run_parser_quality_eval_writes_artifacts(tmp_path: Path, monkeypatch) -> None:
    parsed_dir = tmp_path / "parsed"
    parsed_dir.mkdir()
    out_dir = tmp_path / "quality"

    def fake_evaluate_parser_quality(parsed_dir_arg, *, quality_threshold: float = 0.6):
        assert parsed_dir_arg == parsed_dir
        return (
            [
                {
                    "doc_id": "doc:000",
                    "quality_score": 0.95,
                    "page_citation_available": True,
                    "visual_content_present": False,
                    "risk_flags": [],
                }
            ],
            {
                "doc_count": 1,
                "quality_threshold": quality_threshold,
                "average_quality_score": 0.95,
                "low_quality_doc_count": 0,
                "page_citation_available_count": 1,
                "page_citation_coverage": 1.0,
                "visual_content_doc_count": 0,
                "risk_flag_counts": {},
            },
        )

    monkeypatch.setattr(
        cli_module, "evaluate_parser_quality", fake_evaluate_parser_quality
    )

    summary = run_parser_quality_eval(parsed_dir, out_dir, quality_threshold=0.7)

    assert summary["quality_threshold"] == 0.7
    assert json.loads((out_dir / "summary.json").read_text(encoding="utf-8")) == summary
    assert (out_dir / "per_doc.jsonl").is_file()
    assert (out_dir / "risky_docs.jsonl").is_file()


def test_main_prints_quality_summary_json(tmp_path: Path, monkeypatch, capsys) -> None:
    parsed_dir = tmp_path / "parsed"
    parsed_dir.mkdir()

    def fake_run_parser_quality_eval(
        parsed_dir_arg, out_dir_arg, *, quality_threshold: float = 0.6
    ):
        assert parsed_dir_arg == parsed_dir
        assert out_dir_arg == tmp_path / "quality"
        return {
            "doc_count": 1,
            "quality_threshold": quality_threshold,
            "average_quality_score": 0.9,
            "low_quality_doc_count": 0,
            "page_citation_available_count": 1,
            "page_citation_coverage": 1.0,
            "visual_content_doc_count": 0,
            "risk_flag_counts": {},
        }

    monkeypatch.setattr(
        cli_module, "run_parser_quality_eval", fake_run_parser_quality_eval
    )

    rc = main(
        [
            "--parsed-dir",
            str(parsed_dir),
            "--out",
            str(tmp_path / "quality"),
            "--quality-threshold",
            "0.7",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["quality_threshold"] == 0.7
    assert payload["average_quality_score"] == 0.9
