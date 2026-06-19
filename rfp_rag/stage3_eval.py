from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Iterable

from .evaluate import (
    DEFAULT_REAL_RETRY_ATTEMPTS,
    JUDGED_LANES,
    MAX_ERROR_RATE,
    _answer_error_warning,
    _by_type,
    _call_with_retries,
    _env_float,
    _env_int,
    _files_path_from_index,
    _index_embedding_lane,
    _lane_aggregate,
    _score_distribution,
    _score_prediction,
)
from .providers import (
    build_embeddings,
    build_generator,
    embedding_model_name,
    generation_model_name,
    normalize_lane,
    prompt_template_hash,
)
from .rag_chain import answer_with_store
from .rerank import RERANKER_NONE, RERANKERS, build_reranker
from .stage3_holdout import STAGE3_CONTRACT_VERSION, THRESHOLDS, audit_stage3_cases
from .vector_index import RETRIEVAL_MODES, RETRIEVAL_VECTOR, load_vector_store
from .visual_sidecar import load_reviewed_visual_evidence


DEFAULT_CASES = Path("eval_sets/stage3_holdout/cases.jsonl")
DEFAULT_INDEX = Path("artifacts/index_real")
DEFAULT_OUT = Path("artifacts/eval_stage3_raw")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def load_fixed_stage3_cases(cases_path: Path | str) -> list[dict[str, Any]]:
    rows = _read_jsonl(Path(cases_path))
    cases: list[dict[str, Any]] = []
    optional_fields = [
        "expected_field",
        "expected_value_raw",
        "expected_value_normalized",
        "expected_values_normalized",
        "expected_section_types",
        "expected_section_titles",
        "expected_visual_record_ids",
        "expected_visual_types",
        "expected_visual_pages",
        "required_phrase",
        "required_warning",
    ]
    for row in rows:
        case = {
            "id": row["id"],
            "query": row["query"],
            "query_type": row["query_type"],
            "expected_doc_ids": list(row.get("expected_doc_ids") or []),
            "label_source": row["label_source"],
        }
        for field in optional_fields:
            if field in row:
                case[field] = row[field]
        cases.append(case)
    return cases


def _judge_model_name(lane: str) -> str:
    if lane not in JUDGED_LANES:
        return "not_applicable"
    from .judge import DEFAULT_JUDGE_MODEL

    return os.environ.get("RFP_JUDGE_MODEL", DEFAULT_JUDGE_MODEL)


def _unsupported_visual_claim_rate(predictions: list[dict[str, Any]]) -> float:
    visual_predictions = [
        pred
        for pred in predictions
        if pred.get("query_type") == "visual_table"
        and pred.get("expected_visual_record_ids")
    ]
    if not visual_predictions:
        return 0.0
    unsupported = 0
    for pred in visual_predictions:
        expected = {str(item) for item in pred.get("expected_visual_record_ids") or []}
        cited: set[str] = set()
        for source in pred.get("sources") or []:
            for evidence in source.get("visual_evidence") or []:
                record_id = evidence.get("record_id")
                if record_id is not None:
                    cited.add(str(record_id))
        if not cited.intersection(expected):
            unsupported += 1
    return unsupported / len(visual_predictions)


def _abstention_precision(predictions: list[dict[str, Any]]) -> float:
    abstentions = [
        pred for pred in predictions if pred.get("query_type") == "abstention"
    ]
    if not abstentions:
        return 0.0
    passed = sum(
        1
        for pred in abstentions
        if (pred.get("pass_fail") or {}).get("abstention_pass") == 1.0
    )
    return passed / len(abstentions)


def _query_set_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {"total": len(cases)}
    for case in cases:
        query_type = str(case.get("query_type") or "unknown")
        counts[query_type] = counts.get(query_type, 0) + 1
    return counts


def _validate_stage3_cases(root: Path, cases_path: Path) -> dict[str, Any]:
    audit = audit_stage3_cases(root=root, cases_path=cases_path)
    if not audit["stage3_case_audit_complete"]:
        failed = ", ".join(audit.get("failed") or [])
        raise ValueError(f"stage3 cases failed audit: {failed}")
    return audit


def evaluate_stage3_cases(
    *,
    cases_path: Path | str = DEFAULT_CASES,
    index_dir: Path | str = DEFAULT_INDEX,
    out_dir: Path | str = DEFAULT_OUT,
    provider: str = "real_openai",
    top_k: int = 5,
    min_score: float = 0.47,
    retrieval_mode: str = RETRIEVAL_VECTOR,
    reranker: str = RERANKER_NONE,
    rerank_candidate_k: int | None = None,
    visual_records_path: Path | str | None = None,
    root: Path | str = Path("."),
) -> dict[str, Any]:
    if retrieval_mode not in RETRIEVAL_MODES:
        raise ValueError(f"unknown retrieval_mode: {retrieval_mode}")
    if reranker not in RERANKERS:
        raise ValueError(f"unknown reranker: {reranker}")

    root = Path(root).resolve()
    cases_path = Path(cases_path)
    index_dir = Path(index_dir)
    out_dir = Path(out_dir)
    audit = _validate_stage3_cases(root, cases_path)
    cases = load_fixed_stage3_cases(cases_path)

    lane = normalize_lane(provider)
    index_lane = _index_embedding_lane(index_dir)
    if lane != index_lane:
        raise ValueError(
            f"provider lane {lane!r} does not match index embedding lane {index_lane!r}; rebuild the index"
        )
    _files_path_from_index(index_dir)

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "cases.jsonl", cases)

    store = load_vector_store(index_dir / "qdrant", build_embeddings(lane), lane=lane)
    generator = build_generator(lane)
    reranker_impl = build_reranker(lane, reranker)
    visual_evidence_index = (
        load_reviewed_visual_evidence(visual_records_path)
        if visual_records_path is not None
        else None
    )
    response_reranker = reranker_impl.name if reranker_impl else RERANKER_NONE
    response_rerank_candidate_k = rerank_candidate_k or top_k

    retry_attempts = _env_int("RFP_EVAL_ANSWER_RETRY_ATTEMPTS", 1)
    retry_base_delay = _env_float("RFP_EVAL_ANSWER_RETRY_DELAY_SECONDS", 0.0)
    call_delay = _env_float("RFP_EVAL_ANSWER_DELAY_SECONDS", 0.0)
    if lane in JUDGED_LANES:
        retry_attempts = _env_int(
            "RFP_EVAL_ANSWER_RETRY_ATTEMPTS", DEFAULT_REAL_RETRY_ATTEMPTS
        )

    predictions: list[dict[str, Any]] = []
    error_count = 0
    for record in cases:
        try:
            response = _call_with_retries(
                lambda: answer_with_store(
                    store,
                    generator,
                    record["query"],
                    top_k=top_k,
                    min_score=min_score,
                    retrieval_mode=retrieval_mode,
                    index_dir=index_dir,
                    reranker=reranker_impl,
                    rerank_candidate_k=rerank_candidate_k,
                    visual_evidence_index=visual_evidence_index,
                    preserve_generator_abstention_sources=bool(
                        record.get("expected_doc_ids")
                    ),
                ),
                max_attempts=retry_attempts,
                base_delay_seconds=retry_base_delay,
            )
        except Exception as exc:  # noqa: BLE001 - isolate per-question API failures
            error_count += 1
            response = {
                "query": record["query"],
                "answer": "",
                "sources": [],
                "warnings": [_answer_error_warning(exc)],
                "confidence": "low",
                "retrieved_doc_ids": [],
                "retrieved_chunk_ids": [],
                "scores": [],
                "reranker": response_reranker,
                "rerank_candidate_k": response_rerank_candidate_k,
                "reranker_scores": [],
            }
        pass_fail = _score_prediction(record, response, top_k=top_k)
        predictions.append(
            {
                "query_id": record["id"],
                "query": record["query"],
                "query_type": record["query_type"],
                "expected_doc_ids": record.get("expected_doc_ids", []),
                "expected_section_types": record.get("expected_section_types", []),
                "expected_section_titles": record.get("expected_section_titles", []),
                "expected_visual_record_ids": record.get(
                    "expected_visual_record_ids", []
                ),
                "expected_visual_types": record.get("expected_visual_types", []),
                "expected_visual_pages": record.get("expected_visual_pages", []),
                "retrieved_doc_ids": response.get("retrieved_doc_ids", []),
                "retrieved_chunk_ids": response.get("retrieved_chunk_ids", []),
                "answer": response.get("answer", ""),
                "sources": response.get("sources", []),
                "source_texts": response.get("source_texts", []),
                "warnings": response.get("warnings", []),
                "scores": response.get("scores", []),
                "reranker": response.get("reranker", RERANKER_NONE),
                "rerank_candidate_k": response.get("rerank_candidate_k"),
                "reranker_scores": response.get("reranker_scores", []),
                "pass_fail": pass_fail,
            }
        )
        if call_delay:
            time.sleep(call_delay)

    if lane in JUDGED_LANES:
        from .judge import judge_predictions

        judge_start_delay = _env_float("RFP_EVAL_JUDGE_START_DELAY_SECONDS", 0.0)
        if judge_start_delay:
            time.sleep(judge_start_delay)
        predictions = judge_predictions(predictions)

    error_rate = error_count / len(cases) if cases else 0.0
    evaluation_valid = error_rate <= MAX_ERROR_RATE
    aggregate = _lane_aggregate(lane, predictions)
    aggregate["unsupported_visual_claim_rate"] = _unsupported_visual_claim_rate(
        predictions
    )
    aggregate["abstention_precision"] = _abstention_precision(predictions)
    metrics = {
        "contract_version": STAGE3_CONTRACT_VERSION,
        "provider_lane": lane,
        "generation_model_id": generation_model_name(lane),
        "judge_model_id": _judge_model_name(lane),
        "embedding_model_id": embedding_model_name(lane),
        "prompt_template_hash": prompt_template_hash(),
        "top_k": top_k,
        "min_score": min_score,
        "retrieval_mode": retrieval_mode,
        "reranker": reranker,
        "rerank_candidate_k": rerank_candidate_k or top_k,
        "cases_path": _display_path(cases_path, root),
        "index_dir": _display_path(index_dir, root),
        "eval_set_hash": audit["eval_set_hash"],
        "query_set_counts": _query_set_counts(cases),
        "error_rate": error_rate,
        "evaluation_valid": evaluation_valid,
        "aggregate": aggregate,
        "per_type": _by_type(predictions),
        "score_distribution": _score_distribution(predictions),
        "thresholds": dict(THRESHOLDS),
    }
    _write_json(out_dir / "metrics.json", metrics)
    _write_jsonl(out_dir / "predictions.jsonl", predictions)
    return metrics


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the fixed Stage 3 independent holdout evaluation set."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--provider", default="real_openai")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-score", type=float, default=0.47)
    parser.add_argument(
        "--retrieval-mode",
        choices=sorted(RETRIEVAL_MODES),
        default=RETRIEVAL_VECTOR,
    )
    parser.add_argument("--reranker", choices=sorted(RERANKERS), default=RERANKER_NONE)
    parser.add_argument("--rerank-candidate-k", type=int)
    parser.add_argument("--visual-records", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    metrics = evaluate_stage3_cases(
        root=args.root,
        cases_path=args.cases,
        index_dir=args.index,
        out_dir=args.out,
        provider=args.provider,
        top_k=args.top_k,
        min_score=args.min_score,
        retrieval_mode=args.retrieval_mode,
        reranker=args.reranker,
        rerank_candidate_k=args.rerank_candidate_k,
        visual_records_path=args.visual_records,
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if metrics["evaluation_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
