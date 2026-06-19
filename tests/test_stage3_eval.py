from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rfp_rag import stage3_eval


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _cases(doc_count: int = 20, query_count: int = 100) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx in range(query_count):
        doc_id = f"stage3-doc-{idx % doc_count:03d}"
        query_type = "abstention" if idx == 0 else "text"
        rows.append(
            {
                "id": f"stage3-{idx:03d}",
                "query": f"독립 평가 질문 {idx}",
                "query_type": query_type,
                "expected_doc_ids": [doc_id],
                "required_phrase": "없는 정보",
                "required_warning": "insufficient_context",
                "label_source": "manual_blind_label",
                "provenance": {
                    "corpus_split": "stage3_independent_holdout",
                    "stage2_overlap": False,
                },
            }
        )
    return rows


def test_load_fixed_stage3_cases_preserves_required_fields(tmp_path: Path) -> None:
    cases_path = tmp_path / "eval_sets/stage3_holdout/cases.jsonl"
    _write_jsonl(cases_path, _cases(query_count=1))

    cases = stage3_eval.load_fixed_stage3_cases(cases_path)

    assert cases == [
        {
            "id": "stage3-000",
            "query": "독립 평가 질문 0",
            "query_type": "abstention",
            "expected_doc_ids": ["stage3-doc-000"],
            "label_source": "manual_blind_label",
            "required_phrase": "없는 정보",
            "required_warning": "insufficient_context",
        }
    ]


def test_evaluate_stage3_cases_runs_fixed_set_with_injected_components(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases_path = tmp_path / "eval_sets/stage3_holdout/cases.jsonl"
    index_dir = tmp_path / "artifacts/index"
    out_dir = tmp_path / "artifacts/eval_stage3_raw"
    _write_jsonl(cases_path, _cases())
    _write_json(
        index_dir / "manifest.json",
        {
            "embedding_provider": "offline",
            "files_path": "data/files",
        },
    )
    (index_dir / "qdrant").mkdir(parents=True)

    monkeypatch.setattr(stage3_eval, "_index_embedding_lane", lambda _index: "offline")
    monkeypatch.setattr(
        stage3_eval, "_files_path_from_index", lambda _index: Path("data/files")
    )
    monkeypatch.setattr(
        stage3_eval, "load_vector_store", lambda *_args, **_kwargs: object()
    )
    monkeypatch.setattr(stage3_eval, "build_embeddings", lambda _lane: object())
    monkeypatch.setattr(stage3_eval, "build_generator", lambda _lane: object())
    monkeypatch.setattr(stage3_eval, "build_reranker", lambda *_args, **_kwargs: None)

    def fake_answer_with_store(*args: Any, **kwargs: Any) -> dict[str, Any]:
        question = args[2] if len(args) > 2 else kwargs["query"]
        idx = int(str(question).split()[-1])
        if idx == 0:
            doc_id = "stage3-doc-000"
            chunk_id = f"{doc_id}:chunk-0"
            return {
                "answer": "없는 정보입니다.",
                "confidence": "low",
                "warnings": ["insufficient_context"],
                "sources": [],
                "retrieved_doc_ids": [doc_id],
                "retrieved_chunk_ids": [chunk_id],
                "scores": [],
                "reranker": "none",
            }
        doc_id = f"stage3-doc-{idx % 20:03d}"
        chunk_id = f"{doc_id}:chunk-0"
        return {
            "answer": "근거 기반 답변",
            "confidence": "high",
            "warnings": [],
            "sources": [{"doc_id": doc_id, "chunk_id": chunk_id}],
            "retrieved_doc_ids": [doc_id],
            "retrieved_chunk_ids": [chunk_id],
            "scores": [0.99],
            "reranker": "none",
        }

    monkeypatch.setattr(stage3_eval, "answer_with_store", fake_answer_with_store)

    metrics = stage3_eval.evaluate_stage3_cases(
        cases_path=cases_path,
        index_dir=index_dir,
        out_dir=out_dir,
        provider="offline",
        top_k=5,
        min_score=0.34,
    )

    assert metrics["query_set_counts"]["total"] == 100
    assert metrics["aggregate"]["recall@5"] == 1.0
    assert metrics["aggregate"]["citation_validity"] == 1.0
    assert metrics["aggregate"]["abstention_precision"] == 1.0
    assert (out_dir / "metrics.json").is_file()
    assert (out_dir / "predictions.jsonl").is_file()
    assert (out_dir / "cases.jsonl").is_file()


def test_evaluate_stage3_cases_rejects_unfrozen_cases(tmp_path: Path) -> None:
    rows = _cases()
    rows[0]["provenance"]["stage2_overlap"] = True
    cases_path = tmp_path / "eval_sets/stage3_holdout/cases.jsonl"
    _write_jsonl(cases_path, rows)

    with pytest.raises(ValueError, match="stage3 cases failed audit"):
        stage3_eval.evaluate_stage3_cases(
            cases_path=cases_path,
            index_dir=tmp_path / "artifacts/index",
            out_dir=tmp_path / "artifacts/eval_stage3_raw",
            provider="offline",
        )
