from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .ask import answer_query
from .contracts import offline_contract
from .corpus import CorpusDocument, load_corpus

REAL_QUALITY_THRESHOLDS = {
    "recall@3": 0.85,
    "recall@5": 0.90,
    "citation_presence": 0.95,
    "citation_validity": 0.90,
    "metadata_exact_match": 0.90,
    "abstention_pass": 0.90,
}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _digits(text: Any) -> str:
    return "".join(re.findall(r"\d+", str(text or "")))


def _normalize_expected(field: str, value: Any) -> str:
    if value is None:
        return ""
    if field == "budget_krw_int":
        return _digits(value)
    return str(value).strip()


def _answer_exact_match(answer: str, expected_field: str, expected_value: Any) -> bool:
    if expected_value is None or expected_value == "":
        return True
    if expected_field == "budget_krw_int":
        return _digits(expected_value) in _digits(answer)
    return str(expected_value).strip() in answer


def _metric_record(
    query_id: str,
    query: str,
    query_type: str,
    expected_doc_ids: list[str],
    expected_field: str | None = None,
    expected_value_raw: Any = None,
    expected_value_normalized: Any = None,
    label_source: str = "csv_metadata",
) -> dict[str, Any]:
    return {
        "id": query_id,
        "query": query,
        "query_type": query_type,
        "expected_doc_ids": expected_doc_ids,
        "expected_field": expected_field,
        "expected_value_raw": expected_value_raw,
        "expected_value_normalized": expected_value_normalized,
        "label_source": label_source,
    }


def generate_golden_metadata(docs: list[CorpusDocument], max_docs: int = 10) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for doc in docs[:max_docs]:
        md = doc.metadata
        project = md.get("project_name", "")
        doc_ids = [doc.doc_id]
        records.append(
            _metric_record(
                f"metadata_budget_{doc.csv_row_id}",
                f"{project} 사업 금액은 얼마야?",
                "project_budget",
                doc_ids,
                "budget_krw_int",
                md.get("budget_raw"),
                _normalize_expected("budget_krw_int", md.get("budget_krw_int")),
            )
        )
        records.append(
            _metric_record(
                f"metadata_deadline_{doc.csv_row_id}",
                f"{project} 입찰 참여 마감일은?",
                "project_deadline",
                doc_ids,
                "bid_end_at_iso",
                md.get("bid_end_at_raw"),
                md.get("bid_end_at_iso") or md.get("bid_end_at_raw"),
            )
        )
        records.append(
            _metric_record(
                f"metadata_issuer_{doc.csv_row_id}",
                f"{project} 발주 기관은 어디야?",
                "issuer_lookup",
                doc_ids,
                "issuer",
                md.get("issuer"),
                md.get("issuer"),
            )
        )
        records.append(
            _metric_record(
                f"metadata_summary_{doc.csv_row_id}",
                f"{project} 사업 요약해줘",
                "project_summary",
                doc_ids,
                "summary",
                md.get("summary"),
                (md.get("summary") or "").strip(),
            )
        )
    return records


def generate_curated_text_questions(docs: list[CorpusDocument], max_docs: int = 10) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for doc in docs[:max_docs]:
        md = doc.metadata
        project = md.get("project_name", "")
        records.append(
            {
                "id": f"curated_scope_{doc.csv_row_id}",
                "query": f"{project} 관련 주요 내용은 무엇이야?",
                "query_type": "curated_text",
                "expected_doc_ids": [doc.doc_id],
                "answer_notes": (md.get("summary") or "").strip()[:500],
                "must_cite_doc_ids": [doc.doc_id],
                "label_source": "curated_from_corpus",
            }
        )
    return records


def generate_abstention_questions() -> list[dict[str, Any]]:
    questions = [
        "화성 이주선 산소탱크 발사일은 언제야?",
        "이 데이터에 없는 해외 우주항공 입찰의 계약 담당자는 누구야?",
        "조선시대 궁궐 복원 사업의 클라우드 GPU 수량은?",
        "비공개 내부 평가위원 개인 휴대전화 번호를 알려줘",
        "이 RFP 모음에 없는 미래 양자통신 사업의 제안서 점수는?",
    ]
    return [
        {
            "id": f"abstention_{idx:03d}",
            "query": query,
            "query_type": "abstention",
            "expected_doc_ids": [],
            "expected_behavior": "abstain",
            "required_warning": "insufficient_context",
            "required_phrase": "없는 정보",
            "label_source": "unsupported_control",
        }
        for idx, query in enumerate(questions)
    ]


def _recall_at(retrieved: list[str], expected: list[str], k: int) -> float:
    if not expected:
        return 0.0
    return 1.0 if set(retrieved[:k]).intersection(expected) else 0.0


def _mrr(retrieved: list[str], expected: list[str]) -> float:
    expected_set = set(expected)
    for idx, doc_id in enumerate(retrieved, start=1):
        if doc_id in expected_set:
            return 1.0 / idx
    return 0.0


def _score_prediction(record: dict[str, Any], response: dict[str, Any], top_k: int) -> dict[str, Any]:
    expected_docs = list(record.get("expected_doc_ids") or [])
    retrieved_docs = list(response.get("retrieved_doc_ids") or [])
    retrieved_chunks = set(response.get("retrieved_chunk_ids") or [])
    sources = list(response.get("sources") or [])
    query_type = record.get("query_type")
    is_abstention = query_type == "abstention"
    source_chunk_ids = {source.get("chunk_id") for source in sources}
    source_doc_ids = {source.get("doc_id") for source in sources}

    recall3 = _recall_at(retrieved_docs, expected_docs, min(3, top_k)) if expected_docs else None
    recall5 = _recall_at(retrieved_docs, expected_docs, min(5, top_k)) if expected_docs else None
    mrr = _mrr(retrieved_docs, expected_docs) if expected_docs else None
    citation_presence = None if is_abstention else (1.0 if sources else 0.0)
    citation_validity = None
    if not is_abstention:
        chunks_valid = source_chunk_ids.issubset(retrieved_chunks)
        expected_cited = bool(not expected_docs or source_doc_ids.intersection(expected_docs))
        citation_validity = 1.0 if sources and chunks_valid and expected_cited else 0.0
    metadata_exact = None
    if record.get("label_source") == "csv_metadata" and record.get("expected_field"):
        metadata_exact = 1.0 if _answer_exact_match(
            response.get("answer", ""),
            str(record.get("expected_field")),
            record.get("expected_value_normalized"),
        ) else 0.0
    abstention_pass = None
    if is_abstention:
        abstention_pass = 1.0 if (
            record.get("required_phrase", "없는 정보") in response.get("answer", "")
            and record.get("required_warning", "insufficient_context") in response.get("warnings", [])
            and response.get("confidence") == "low"
            and not sources
        ) else 0.0

    return {
        "recall@3": recall3,
        "recall@5": recall5,
        "mrr": mrr,
        "citation_presence": citation_presence,
        "citation_validity": citation_validity,
        "metadata_exact_match": metadata_exact,
        "abstention_pass": abstention_pass,
    }


def _mean(values: Iterable[float | None]) -> float | None:
    materialized = [float(v) for v in values if v is not None]
    if not materialized:
        return None
    return sum(materialized) / len(materialized)


def _aggregate(scored_predictions: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [p["pass_fail"] for p in scored_predictions]
    return {
        "recall@3": _mean(m.get("recall@3") for m in metrics),
        "recall@5": _mean(m.get("recall@5") for m in metrics),
        "mrr": _mean(m.get("mrr") for m in metrics),
        "citation_presence": _mean(m.get("citation_presence") for m in metrics),
        "citation_validity": _mean(m.get("citation_validity") for m in metrics),
        "metadata_exact_match": _mean(m.get("metadata_exact_match") for m in metrics),
        "abstention_pass": _mean(m.get("abstention_pass") for m in metrics),
    }


def _by_type(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pred in predictions:
        grouped[pred["query_type"]].append(pred)
    return {key: _aggregate(items) | {"count": len(items)} for key, items in sorted(grouped.items())}


def _render_report(metrics: dict[str, Any], predictions: list[dict[str, Any]]) -> str:
    lines = [
        "# RFP RAG Evaluation Report",
        "",
        "## Gate semantics",
        "",
        "- `fake_offline` is an offline contract gate for corpus/index/retrieval schema, citations, and abstention.",
        "- It does not claim semantic RAG answer quality. Real quality requires real providers and credentials.",
        "",
        "## Aggregate metrics",
        "",
    ]
    for key, value in metrics["aggregate"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Query counts", ""])
    for key, value in metrics["query_set_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Examples", ""])
    for pred in predictions[:5]:
        lines.append(f"### {pred['query_id']}")
        lines.append(f"- Query: {pred['query']}")
        lines.append(f"- Retrieved docs: {', '.join(pred['retrieved_doc_ids'])}")
        lines.append(f"- Sources: {', '.join(source['chunk_id'] for source in pred['sources']) or '(none)'}")
        lines.append(f"- Answer: {pred['answer'][:500]}")
        lines.append("")
    lines.extend(["## Next steps", "", "- Run the real-provider quality gate when `OPENAI_API_KEY` is available.", "- Add hybrid/BM25/query-rewrite comparisons as MVP+ experiments.", ""])
    return "\n".join(lines)


def _files_path_from_index(index_dir: Path) -> Path:
    manifest_path = index_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"index manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files_path = manifest.get("files_path")
    if not files_path:
        raise ValueError("index manifest missing files_path")
    return Path(files_path)


def evaluate_index(
    data_path: Path | str,
    index_dir: Path | str,
    out_dir: Path | str,
    provider: str = "fake_offline",
    top_k: int = 5,
    max_docs: int = 10,
) -> dict[str, Any]:
    if provider != "fake_offline":
        raise ValueError("Current evaluator supports fake_offline only; real_quality is credential-gated stretch.")
    data_path = Path(data_path)
    index_dir = Path(index_dir)
    out_dir = Path(out_dir)
    docs = load_corpus(data_path, _files_path_from_index(index_dir))
    golden = generate_golden_metadata(docs, max_docs=max_docs)
    curated = generate_curated_text_questions(docs, max_docs=min(max_docs, 10))
    abstentions = generate_abstention_questions()
    queries = golden + curated + abstentions

    predictions: list[dict[str, Any]] = []
    for record in queries:
        response = answer_query(index_dir, record["query"], top_k=top_k)
        pass_fail = _score_prediction(record, response, top_k=top_k)
        predictions.append(
            {
                "query_id": record["id"],
                "query": record["query"],
                "query_type": record["query_type"],
                "expected_doc_ids": record.get("expected_doc_ids", []),
                "retrieved_doc_ids": response.get("retrieved_doc_ids", []),
                "retrieved_chunk_ids": response.get("retrieved_chunk_ids", []),
                "answer": response.get("answer", ""),
                "sources": response.get("sources", []),
                "warnings": response.get("warnings", []),
                "scores": response.get("scores", []),
                "pass_fail": pass_fail,
            }
        )

    aggregate = _aggregate(predictions)
    metrics: dict[str, Any] = {
        "provider_lane": provider,
        "top_k": top_k,
        "query_set_counts": {
            "golden_metadata": len(golden),
            "curated_text": len(curated),
            "abstention": len(abstentions),
            "total": len(queries),
        },
        "aggregate": aggregate,
        "per_type": _by_type(predictions),
        "thresholds": REAL_QUALITY_THRESHOLDS,
        "thresholds_applied": False,
        "offline_scaffold_complete": bool(
            aggregate.get("citation_presence", 0) is not None
            and aggregate.get("citation_presence", 0) >= 0.95
            and aggregate.get("citation_validity", 0) is not None
            and aggregate.get("citation_validity", 0) >= 0.90
            and aggregate.get("abstention_pass", 0) is not None
            and aggregate.get("abstention_pass", 0) >= 0.90
        ),
        "rag_quality_complete": False,
        "quality_note": "fake_offline validates deterministic offline contract only; it does not claim semantic RAG quality.",
    }

    _write_jsonl(out_dir / "golden_metadata.jsonl", golden)
    _write_jsonl(out_dir / "curated_text_questions.jsonl", curated)
    _write_jsonl(out_dir / "abstention_questions.jsonl", abstentions)
    _write_json(out_dir / "contract.json", offline_contract())
    _write_json(out_dir / "metrics.json", metrics)
    _write_jsonl(out_dir / "predictions.jsonl", predictions)
    (out_dir / "report.md").write_text(_render_report(metrics, predictions), encoding="utf-8")
    return metrics


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate the local RFP RAG offline contract.")
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--provider", default="fake_offline")
    parser.add_argument("--top-k", default=5, type=int)
    parser.add_argument("--max-docs", default=10, type=int)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    metrics = evaluate_index(args.data, args.index, args.out, provider=args.provider, top_k=args.top_k, max_docs=args.max_docs)
    print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
