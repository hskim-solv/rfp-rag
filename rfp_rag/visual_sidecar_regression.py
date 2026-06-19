from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .evaluate import _index_embedding_lane, _score_prediction
from .providers import build_embeddings, build_generator
from .rag_chain import answer_with_store
from .vector_index import RETRIEVAL_VECTOR, load_vector_store
from .visual_sidecar import load_reviewed_visual_evidence


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on {path}:{line_number}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"jsonl row must be an object on {path}:{line_number}")
            rows.append(row)
    return rows


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


def _mean(values: Iterable[float | None]) -> float | None:
    materialized = [float(value) for value in values if value is not None]
    if not materialized:
        return None
    return sum(materialized) / len(materialized)


def _metric(
    predictions: list[dict[str, Any]],
    *,
    query_type: str,
    metric: str,
) -> float | None:
    return _mean(
        (prediction.get("pass_fail") or {}).get(metric)
        for prediction in predictions
        if prediction.get("query_type") == query_type
    )


def compare_sidecar_predictions(
    *,
    sidecar_on: list[dict[str, Any]],
    sidecar_off: list[dict[str, Any]],
    min_citation_validity: float = 0.90,
    min_abstention_pass: float = 1.0,
) -> dict[str, Any]:
    on_ids = {str(row.get("query_id")) for row in sidecar_on}
    off_ids = {str(row.get("query_id")) for row in sidecar_off}
    query_set_match = on_ids == off_ids and bool(on_ids)
    citation_on = _metric(
        sidecar_on, query_type="visual_table", metric="citation_validity"
    )
    citation_off = _metric(
        sidecar_off, query_type="visual_table", metric="citation_validity"
    )
    abstention_on = _metric(
        sidecar_on, query_type="abstention", metric="abstention_pass"
    )
    abstention_off = _metric(
        sidecar_off, query_type="abstention", metric="abstention_pass"
    )

    citation_no_regression = (
        query_set_match
        and citation_on is not None
        and citation_off is not None
        and citation_on >= citation_off
        and citation_on >= min_citation_validity
    )
    abstention_no_regression = (
        query_set_match
        and abstention_on is not None
        and abstention_off is not None
        and abstention_on >= abstention_off
        and abstention_on >= min_abstention_pass
    )
    failed: list[str] = []
    if not citation_no_regression:
        failed.append("sidecar_citation_no_regression")
    if not abstention_no_regression:
        failed.append("sidecar_abstention_no_regression")

    return {
        "visual_sidecar_regression_complete": not failed,
        "sidecar_citation_no_regression": citation_no_regression,
        "sidecar_abstention_no_regression": abstention_no_regression,
        "metrics": {
            "sidecar_on_visual_citation_validity": citation_on,
            "sidecar_off_visual_citation_validity": citation_off,
            "sidecar_on_abstention_pass": abstention_on,
            "sidecar_off_abstention_pass": abstention_off,
            "query_set_match": 1.0 if query_set_match else 0.0,
        },
        "thresholds": {
            "sidecar_on_visual_citation_validity": min_citation_validity,
            "sidecar_on_abstention_pass": min_abstention_pass,
            "query_set_match": 1.0,
        },
        "query_counts": {
            "sidecar_on": len(sidecar_on),
            "sidecar_off": len(sidecar_off),
            "visual_table": sum(
                1 for row in sidecar_on if row.get("query_type") == "visual_table"
            ),
            "abstention": sum(
                1 for row in sidecar_on if row.get("query_type") == "abstention"
            ),
        },
        "failed": failed,
    }


def _prediction_record(
    *,
    query: dict[str, Any],
    response: dict[str, Any],
    pass_fail: dict[str, Any],
    condition: str,
) -> dict[str, Any]:
    query_text = str(query.get("query") or "")
    return {
        "condition": condition,
        "query_id": query.get("id"),
        "query_hash": hashlib.sha256(query_text.encode("utf-8")).hexdigest(),
        "query_type": query.get("query_type"),
        "expected_doc_ids": query.get("expected_doc_ids") or [],
        "retrieved_doc_ids": response.get("retrieved_doc_ids") or [],
        "retrieved_chunk_ids": response.get("retrieved_chunk_ids") or [],
        "source_count": len(response.get("sources") or []),
        "warnings": response.get("warnings") or [],
        "confidence": response.get("confidence"),
        "pass_fail": pass_fail,
    }


def _run_condition(
    *,
    queries: list[dict[str, Any]],
    index_dir: Path,
    top_k: int,
    min_score: float,
    visual_records: Path,
    use_sidecar: bool,
) -> list[dict[str, Any]]:
    lane = _index_embedding_lane(index_dir)
    store = load_vector_store(index_dir / "qdrant", build_embeddings(lane), lane=lane)
    generator = build_generator(lane)
    visual_evidence_index = (
        load_reviewed_visual_evidence(visual_records) if use_sidecar else None
    )
    condition = "sidecar_on" if use_sidecar else "sidecar_off"
    predictions: list[dict[str, Any]] = []
    for query in queries:
        response = answer_with_store(
            store,
            generator,
            str(query["query"]),
            top_k=top_k,
            min_score=min_score,
            retrieval_mode=RETRIEVAL_VECTOR,
            index_dir=index_dir,
            visual_evidence_index=visual_evidence_index,
            preserve_generator_abstention_sources=bool(query.get("expected_doc_ids")),
        )
        pass_fail = _score_prediction(query, response, top_k=top_k)
        predictions.append(
            _prediction_record(
                query=query,
                response=response,
                pass_fail=pass_fail,
                condition=condition,
            )
        )
    return predictions


def _load_queries(eval_dir: Path, fallback_eval_dir: Path) -> list[dict[str, Any]]:
    visual = _read_jsonl(eval_dir / "visual_table_questions.jsonl")
    abstention = _read_jsonl(eval_dir / "abstention_questions.jsonl")
    if not abstention:
        abstention = _read_jsonl(fallback_eval_dir / "abstention_questions.jsonl")
    return visual + abstention


def write_sidecar_regression(
    *,
    sidecar_on: list[dict[str, Any]],
    sidecar_off: list[dict[str, Any]],
    out: Path,
) -> dict[str, Any]:
    summary = compare_sidecar_predictions(
        sidecar_on=sidecar_on,
        sidecar_off=sidecar_off,
    )
    _write_json(out, summary)
    return summary


def run_visual_sidecar_regression(
    *,
    index_dir: Path | str,
    visual_records: Path | str,
    eval_dir: Path | str,
    fallback_eval_dir: Path | str,
    out: Path | str,
    predictions_dir: Path | str,
    top_k: int = 5,
    min_score: float = 0.34,
) -> dict[str, Any]:
    queries = _load_queries(Path(eval_dir), Path(fallback_eval_dir))
    if not queries:
        raise ValueError("sidecar regression requires visual or abstention queries")
    predictions_path = Path(predictions_dir)
    sidecar_on = _run_condition(
        queries=queries,
        index_dir=Path(index_dir),
        top_k=top_k,
        min_score=min_score,
        visual_records=Path(visual_records),
        use_sidecar=True,
    )
    sidecar_off = _run_condition(
        queries=queries,
        index_dir=Path(index_dir),
        top_k=top_k,
        min_score=min_score,
        visual_records=Path(visual_records),
        use_sidecar=False,
    )
    _write_jsonl(predictions_path / "sidecar_on_predictions.jsonl", sidecar_on)
    _write_jsonl(predictions_path / "sidecar_off_predictions.jsonl", sidecar_off)
    summary = write_sidecar_regression(
        sidecar_on=sidecar_on,
        sidecar_off=sidecar_off,
        out=Path(out),
    )
    summary["prediction_artifacts"] = [
        str((predictions_path / "sidecar_on_predictions.jsonl")),
        str((predictions_path / "sidecar_off_predictions.jsonl")),
    ]
    _write_json(Path(out), summary)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run offline visual sidecar on/off regression checks."
    )
    parser.add_argument("--index", type=Path, default=Path("artifacts/index"))
    parser.add_argument(
        "--visual-records",
        type=Path,
        default=Path("artifacts/visual_structure_stage2_reviewed/records.jsonl"),
    )
    parser.add_argument("--eval-dir", type=Path, default=Path("artifacts/eval_stage2"))
    parser.add_argument(
        "--fallback-eval-dir", type=Path, default=Path("artifacts/eval")
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("artifacts/visual_quality/sidecar_regression.json"),
    )
    parser.add_argument(
        "--predictions-dir",
        type=Path,
        default=Path("artifacts/visual_quality"),
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-score", type=float, default=0.34)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(list(argv) if argv is not None else None)
    summary = run_visual_sidecar_regression(
        index_dir=args.index,
        visual_records=args.visual_records,
        eval_dir=args.eval_dir,
        fallback_eval_dir=args.fallback_eval_dir,
        out=args.out,
        predictions_dir=args.predictions_dir,
        top_k=args.top_k,
        min_score=args.min_score,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["visual_sidecar_regression_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
