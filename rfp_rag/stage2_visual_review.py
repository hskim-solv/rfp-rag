from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from .corpus import load_corpus
from .evaluate import generate_visual_table_questions
from .visual_facts import _accepted_fact, _read_jsonl, _validate_fact
from .visual_sidecar import load_reviewed_visual_evidence


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _question_from_record(record: dict[str, Any]) -> dict[str, Any]:
    record_id = str(record["record_id"])
    doc_id = str(record["doc_id"])
    page = int(record["page"])
    visual_type = str(record["visual_type"])
    facts = list(record.get("structured_facts") or [])
    fact = facts[0] if facts else {}
    visual_label = visual_type.replace("_", " ")
    return {
        "id": f"visual_table_{doc_id.replace(':', '_')}_p{page}_{visual_type}",
        "query": (
            f"{doc_id} 문서 {page}페이지의 {visual_label} "
            "시각자료가 어떤 정보를 보여주는지 알려줘"
        ),
        "query_type": "visual_table",
        "expected_doc_ids": [doc_id],
        "expected_visual_record_ids": [record_id],
        "expected_visual_types": [visual_type],
        "expected_visual_pages": [page],
        "expected_field": fact.get("field"),
        "expected_value_normalized": str(fact.get("value") or "").strip(),
        "label_source": "stage2_visual_review_gold",
    }


def _existing_fact_count(records: Iterable[dict[str, Any]]) -> int:
    return sum(len(record.get("structured_facts") or []) for record in records)


def merge_stage2_visual_facts(
    records: Iterable[dict[str, Any]],
    facts: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    merged_records = [deepcopy(record) for record in records]
    by_record = {str(record["record_id"]): record for record in merged_records}
    existing_fact_count = _existing_fact_count(merged_records)
    accepted_count = 0
    skipped_count = 0

    for fact in facts:
        record_id = str(fact.get("record_id") or "").strip()
        record = by_record.get(record_id)
        if record is None:
            raise ValueError(f"unknown record_id {record_id!r}")
        _validate_fact(record, fact)
        if str(fact.get("status") or "").strip() != "accepted":
            skipped_count += 1
            continue
        structured_facts = list(record.get("structured_facts") or [])
        structured_facts.append(_accepted_fact(record_id, len(structured_facts), fact))
        record["structured_facts"] = structured_facts
        record["review_status"] = "stage2_reviewed"
        accepted_count += 1

    question_records = [
        record for record in merged_records if record.get("structured_facts")
    ]
    questions = [_question_from_record(record) for record in question_records]
    summary = {
        "stage2_visual_review_complete": True,
        "record_count": len(merged_records),
        "existing_fact_count": existing_fact_count,
        "added_fact_count": accepted_count,
        "skipped_fact_count": skipped_count,
        "total_fact_count": _existing_fact_count(merged_records),
        "visual_table_question_count": len(questions),
    }
    return merged_records, {"summary": summary, "questions": questions}


def run_stage2_visual_review(
    *,
    records_path: Path | str,
    facts_path: Path | str,
    out_dir: Path | str,
    eval_dir: Path | str,
    data_path: Path | str | None = None,
    files_path: Path | str | None = None,
) -> dict[str, Any]:
    records = _read_jsonl(Path(records_path))
    facts = _read_jsonl(Path(facts_path))
    merged_records, payload = merge_stage2_visual_facts(records, facts)
    out = Path(out_dir)
    eval_out = Path(eval_dir)
    records_out = out / "records.jsonl"
    _write_jsonl(records_out, merged_records)
    questions = payload["questions"]
    if data_path is not None and files_path is not None:
        docs = load_corpus(data_path, files_path)
        questions = generate_visual_table_questions(
            docs,
            load_reviewed_visual_evidence(records_out),
        )
        payload["summary"]["visual_table_question_count"] = len(questions)
    _write_json(out / "summary.json", payload["summary"])
    _write_jsonl(eval_out / "visual_table_questions.jsonl", questions)
    _write_json(eval_out / "visual_table_summary.json", payload["summary"])
    return payload["summary"]


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Merge Stage 2 visual review facts and write visual-table eval questions."
    )
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--facts", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--eval-dir", required=True, type=Path)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--files", type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(list(argv) if argv is not None else None)
    summary = run_stage2_visual_review(
        records_path=args.records,
        facts_path=args.facts,
        out_dir=args.out,
        eval_dir=args.eval_dir,
        data_path=args.data,
        files_path=args.files,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
