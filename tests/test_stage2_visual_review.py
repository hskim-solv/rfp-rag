from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.stage2_visual_review import main, run_stage2_visual_review


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _record(record_id: str, *, structured_facts: list[dict] | None = None) -> dict:
    parts = record_id.split(":")
    doc_id = ":".join(parts[:2])
    page_token = parts[2]
    visual_type = ":".join(parts[3:])
    return {
        "record_id": record_id,
        "doc_id": doc_id,
        "page": int(page_token.removeprefix("p")),
        "visual_type": visual_type,
        "business_fields": ["requirements"],
        "structured_facts": structured_facts or [],
        "review_status": "reviewed_needs_extraction",
    }


def test_run_stage2_visual_review_preserves_existing_facts_and_adds_questions(
    tmp_path: Path,
) -> None:
    records_path = tmp_path / "records.jsonl"
    facts_path = tmp_path / "stage2_facts.jsonl"
    out_dir = tmp_path / "reviewed"
    eval_dir = tmp_path / "eval_stage2"
    _write_jsonl(
        records_path,
        [
            _record(
                "doc:001:p1:requirements_table",
                structured_facts=[
                    {
                        "fact_id": "doc:001:p1:requirements_table:fact:000",
                        "fact_type": "visual_type_present",
                        "field": "requirements",
                        "value": "original reviewed fact",
                        "evidence_quote": "original reviewed fact",
                        "reviewer": "stage1",
                        "confidence": 0.9,
                    }
                ],
            ),
            _record("doc:002:p2:requirements_table"),
        ],
    )
    _write_jsonl(
        facts_path,
        [
            {
                "record_id": "doc:002:p2:requirements_table",
                "status": "accepted",
                "fact_type": "visual_type_present",
                "field": "requirements",
                "value": "stage2 reviewed fact",
                "evidence_quote": "stage2 reviewed fact",
                "reviewer": "stage2_visual_review",
                "confidence": 0.86,
            }
        ],
    )

    summary = run_stage2_visual_review(
        records_path=records_path,
        facts_path=facts_path,
        out_dir=out_dir,
        eval_dir=eval_dir,
    )

    merged = _read_jsonl(out_dir / "records.jsonl")
    assert [len(row["structured_facts"]) for row in merged] == [1, 1]
    questions = _read_jsonl(eval_dir / "visual_table_questions.jsonl")
    assert [row["expected_visual_record_ids"][0] for row in questions] == [
        "doc:001:p1:requirements_table",
        "doc:002:p2:requirements_table",
    ]
    assert summary["existing_fact_count"] == 1
    assert summary["added_fact_count"] == 1
    assert summary["visual_table_question_count"] == 2


def test_run_stage2_visual_review_rejects_unknown_record_id(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "records.jsonl", [_record("doc:001:p1:requirements_table")])
    _write_jsonl(
        tmp_path / "facts.jsonl",
        [
            {
                "record_id": "doc:999:p1:requirements_table",
                "status": "accepted",
                "fact_type": "visual_type_present",
                "field": "requirements",
                "value": "bad",
                "evidence_quote": "bad",
                "reviewer": "stage2_visual_review",
            }
        ],
    )

    try:
        run_stage2_visual_review(
            records_path=tmp_path / "records.jsonl",
            facts_path=tmp_path / "facts.jsonl",
            out_dir=tmp_path / "out",
            eval_dir=tmp_path / "eval_stage2",
        )
    except ValueError as exc:
        assert "unknown record_id" in str(exc)
    else:
        raise AssertionError("expected unknown record_id to fail")


def test_stage2_visual_review_cli_writes_artifacts(tmp_path: Path, capsys) -> None:
    records_path = tmp_path / "records.jsonl"
    facts_path = tmp_path / "facts.jsonl"
    _write_jsonl(records_path, [_record("doc:001:p1:requirements_table")])
    _write_jsonl(
        facts_path,
        [
            {
                "record_id": "doc:001:p1:requirements_table",
                "status": "accepted",
                "fact_type": "visual_type_present",
                "field": "requirements",
                "value": "stage2 reviewed fact",
                "evidence_quote": "stage2 reviewed fact",
                "reviewer": "stage2_visual_review",
            }
        ],
    )

    rc = main(
        [
            "--records",
            str(records_path),
            "--facts",
            str(facts_path),
            "--out",
            str(tmp_path / "out"),
            "--eval-dir",
            str(tmp_path / "eval_stage2"),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["stage2_visual_review_complete"] is True
    assert (tmp_path / "out/records.jsonl").is_file()
    assert (tmp_path / "eval_stage2/visual_table_questions.jsonl").is_file()
