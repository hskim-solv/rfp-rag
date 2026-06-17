from __future__ import annotations

import json
from pathlib import Path

import pytest

from rfp_rag.build_index import build_index
from rfp_rag.corpus import CorpusDocument
from rfp_rag.evaluate import (
    _build_arg_parser,
    _call_with_retries,
    _clear_final_eval_artifacts,
    _score_prediction,
    evaluate_index,
    generate_abstention_questions,
    generate_golden_metadata,
    generate_paraphrase_questions,
    generate_section_lookup_questions,
    generate_visual_table_questions,
)
from rfp_rag.rag_chain import AnswerStageError
from rfp_rag.report_check import check_report
from rfp_rag.visual_sidecar import VisualEvidenceIndex


def _build_fake_index(tmp_path: Path, parse_manifest_path: Path) -> Path:
    index_dir = tmp_path / "index"
    build_index(
        data_path=Path("data/data_list.csv"),
        files_path=Path("data/files"),
        out_dir=index_dir,
        chunk_size=500,
        chunk_overlap=80,
        embedding_provider="fake",
        parse_manifest_path=parse_manifest_path,
    )
    return index_dir


def _corpus_doc(i: int) -> CorpusDocument:
    row_id = f"{i:03d}"
    return CorpusDocument(
        csv_row_id=row_id,
        doc_id=f"doc:{row_id}",
        text=f"문서 {i} 본문",
        metadata={
            "project_name": f"프로젝트 {i}",
            "budget_raw": f"{i},000",
            "budget_krw_int": i * 1000,
            "bid_end_at_raw": "2026-01-01 10:00:00",
            "bid_end_at_iso": "2026-01-01T10:00:00",
            "issuer": f"기관 {i}",
            "summary": f"프로젝트 {i} 요약",
        },
    )


def test_default_golden_metadata_benchmark_covers_100_documents() -> None:
    records = generate_golden_metadata([_corpus_doc(i) for i in range(120)])

    assert len(records) == 400
    covered_doc_ids = {
        expected_doc_id
        for record in records
        for expected_doc_id in record["expected_doc_ids"]
    }
    assert covered_doc_ids == {f"doc:{i:03d}" for i in range(100)}


def test_evaluate_cli_default_max_docs_matches_100_document_benchmark() -> None:
    args = _build_arg_parser().parse_args(["--out", "artifacts/eval"])

    assert args.max_docs == 100


def test_abstention_benchmark_has_30_near_domain_hard_negatives() -> None:
    records = generate_abstention_questions()

    assert len(records) == 30
    assert len({record["id"] for record in records}) == 30
    assert {record["query_type"] for record in records} == {"abstention"}
    assert {record["expected_behavior"] for record in records} == {"abstain"}
    near_domain_terms = ("RFP", "입찰", "제안", "평가", "계약", "사업", "발주", "요구")
    near_domain_count = sum(
        any(term in record["query"] for term in near_domain_terms) for record in records
    )
    assert near_domain_count >= 20


def test_default_paraphrase_benchmark_covers_30_metadata_queries() -> None:
    records = generate_paraphrase_questions([_corpus_doc(i) for i in range(40)])

    assert len(records) == 30
    assert len({record["id"] for record in records}) == 30
    assert {record["query_type"] for record in records} == {"paraphrase"}
    assert {record["label_source"] for record in records} == {"csv_metadata"}
    assert {record["expected_doc_ids"][0] for record in records} == {
        f"doc:{i:03d}" for i in range(30)
    }
    assert {record["expected_field"] for record in records} == {
        "bid_end_at_iso",
        "budget_krw_int",
        "issuer",
        "summary",
    }
    assert all("사업 금액은 얼마야?" not in record["query"] for record in records)


def _section_chunk(i: int) -> dict[str, object]:
    section_types = [
        ("project_overview", "사업 개요"),
        ("evaluation_criteria", "평가 기준"),
        ("submission", "제안 제출"),
        ("eligibility", "참가 자격"),
        ("requirements", "요구 사항"),
        ("contract", "계약 조건"),
        ("security", "보안 요구사항"),
    ]
    section_type, section_title = section_types[i % len(section_types)]
    row_id = f"{i:03d}"
    return {
        "chunk_id": f"doc:{row_id}:chunk:0",
        "doc_id": f"doc:{row_id}",
        "csv_row_id": row_id,
        "metadata": {
            "project_name": f"프로젝트 {i}",
            "section_type": section_type,
            "section_title": section_title,
        },
    }


def test_default_section_lookup_benchmark_covers_30_labeled_sections() -> None:
    records = generate_section_lookup_questions([_section_chunk(i) for i in range(40)])

    assert len(records) == 30
    assert len({record["id"] for record in records}) == 30
    assert {record["query_type"] for record in records} == {"section_lookup"}
    assert all(record["expected_section_types"] for record in records)
    assert all(record["expected_section_titles"] for record in records)


def test_multi_doc_scoring_requires_covering_all_expected_docs() -> None:
    record = {
        "query_type": "cross_document",
        "expected_doc_ids": ["doc:a", "doc:b"],
    }
    one_doc_response = {
        "retrieved_doc_ids": ["doc:a", "doc:x"],
        "retrieved_chunk_ids": ["chunk:a"],
        "sources": [{"doc_id": "doc:a", "chunk_id": "chunk:a"}],
    }
    both_docs_response = {
        "retrieved_doc_ids": ["doc:a", "doc:b"],
        "retrieved_chunk_ids": ["chunk:a", "chunk:b"],
        "sources": [
            {"doc_id": "doc:a", "chunk_id": "chunk:a"},
            {"doc_id": "doc:b", "chunk_id": "chunk:b"},
        ],
    }

    partial = _score_prediction(record, one_doc_response, top_k=5)
    complete = _score_prediction(record, both_docs_response, top_k=5)

    assert partial["recall@5"] == 0.5
    assert partial["all_expected_docs_retrieved@5"] == 0.0
    assert complete["recall@5"] == 1.0
    assert complete["all_expected_docs_retrieved@5"] == 1.0


def test_visual_table_questions_are_generated_from_reviewed_gold_evidence() -> None:
    visual_index = VisualEvidenceIndex(
        by_doc_id={
            "doc:040": [
                {
                    "record_id": "doc:040:p10:requirements_table",
                    "doc_id": "doc:040",
                    "page": 10,
                    "visual_type": "requirements_table",
                    "fact_type": "visual_type_present",
                    "field": "requirements",
                    "value": "Requirements table is present on the selected page",
                }
            ]
        }
    )

    records = generate_visual_table_questions([_corpus_doc(40)], visual_index)

    assert records == [
        {
            "id": "visual_table_040_p10_requirements_table",
            "query": "프로젝트 40 문서 10페이지의 요구사항 표 시각자료가 어떤 정보를 보여주는지 알려줘",
            "query_type": "visual_table",
            "expected_doc_ids": ["doc:040"],
            "expected_visual_record_ids": ["doc:040:p10:requirements_table"],
            "expected_visual_types": ["requirements_table"],
            "expected_visual_pages": [10],
            "expected_field": "requirements",
            "expected_value_normalized": (
                "Requirements table is present on the selected page"
            ),
            "label_source": "visual_review_gold",
        }
    ]


def test_visual_table_scoring_checks_attached_visual_evidence_record_ids() -> None:
    record = {
        "query_type": "visual_table",
        "expected_doc_ids": ["doc:040"],
        "expected_visual_record_ids": ["doc:040:p10:requirements_table"],
    }
    no_visual_response = {
        "retrieved_doc_ids": ["doc:040"],
        "retrieved_chunk_ids": ["chunk:040"],
        "sources": [{"doc_id": "doc:040", "chunk_id": "chunk:040"}],
    }
    visual_hit_response = {
        "retrieved_doc_ids": ["doc:040"],
        "retrieved_chunk_ids": ["chunk:040"],
        "sources": [
            {
                "doc_id": "doc:040",
                "chunk_id": "chunk:040",
                "visual_evidence": [
                    {"record_id": "doc:040:p10:requirements_table"},
                ],
            }
        ],
    }

    miss = _score_prediction(record, no_visual_response, top_k=5)
    hit = _score_prediction(record, visual_hit_response, top_k=5)

    assert miss.get("visual_evidence_hit_rate") == 0.0
    assert hit.get("visual_evidence_hit_rate") == 1.0


def test_evaluate_index_writes_offline_contract_artifacts(
    tmp_path: Path, parsed_manifest_factory
) -> None:
    index_dir = _build_fake_index(
        tmp_path, parsed_manifest_factory(Path("data/data_list.csv"))
    )
    eval_dir = tmp_path / "eval"

    metrics = evaluate_index(
        data_path=Path("data/data_list.csv"),
        index_dir=index_dir,
        out_dir=eval_dir,
        provider="fake_offline",  # legacy alias, normalized to the offline lane
        top_k=5,
        max_docs=3,
        min_score=0.34,  # calibrated offline cutoff; rationale recorded in score_distribution
    )

    assert metrics["retrieval_mode"] == "vector"
    assert metrics["reranker"] == "none"
    assert metrics["rerank_candidate_k"] == 5
    saved_metrics = json.loads((eval_dir / "metrics.json").read_text(encoding="utf-8"))
    assert saved_metrics["retrieval_mode"] == "vector"
    assert saved_metrics["reranker"] == "none"
    assert saved_metrics["rerank_candidate_k"] == 5
    report = (eval_dir / "report.md").read_text(encoding="utf-8")
    assert "- retrieval_mode: vector" in report
    assert "- reranker: none" in report
    assert "- rerank_candidate_k: 5" in report
    assert metrics["provider_lane"] == "offline"
    assert metrics["min_score"] == 0.34
    assert metrics["evaluation_valid"] is True
    assert metrics["error_rate"] == 0.0
    assert metrics["offline_scaffold_complete"] is True
    assert metrics["rag_quality_complete"] is False
    assert metrics["thresholds_applied"] is False
    assert metrics["query_set_counts"]["cross_document"] == 20
    assert metrics["query_set_counts"]["abstention"] == 30
    assert metrics["query_set_counts"]["paraphrase"] == 3
    assert metrics["query_set_counts"]["section_lookup"] >= 1
    assert metrics["score_distribution"]["abstention_top_scores"]
    assert metrics["score_distribution"]["in_domain_top_scores"]
    assert metrics["aggregate"]["citation_presence"] >= 0.95
    assert metrics["aggregate"]["citation_validity"] >= 0.90
    assert metrics["aggregate"]["abstention_pass"] >= 0.90
    assert metrics["aggregate"]["all_expected_docs_retrieved@5"] is not None
    assert metrics["aggregate"]["section_hit_rate"] is not None
    assert "cross_document" in metrics["per_type"]
    assert "section_lookup" in metrics["per_type"]
    for name in [
        "golden_metadata.jsonl",
        "curated_text_questions.jsonl",
        "section_lookup_questions.jsonl",
        "cross_document_questions.jsonl",
        "paraphrase_questions.jsonl",
        "abstention_questions.jsonl",
        "eval_progress.jsonl",
        "metrics.json",
        "predictions.jsonl",
        "predictions_unjudged.jsonl",
        "predictions_unjudged_partial.jsonl",
        "predictions_judged_partial.jsonl",
        "report.md",
        "contract.json",
    ]:
        assert (eval_dir / name).exists(), name
    contract = json.loads((eval_dir / "contract.json").read_text(encoding="utf-8"))
    assert saved_metrics == metrics
    assert contract["contract_version"] == "rfp-rag-offline-v4"
    assert contract["quality_semantics"]["offline"]["claims_semantic_quality"] is False


def test_evaluate_index_writes_recoverable_artifacts_before_judge_interrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parsed_manifest_factory
) -> None:
    index_dir = _build_fake_index(
        tmp_path, parsed_manifest_factory(Path("data/data_list.csv"))
    )
    eval_dir = tmp_path / "eval"
    (eval_dir / "metrics.json").parent.mkdir(parents=True)
    (eval_dir / "metrics.json").write_text('{"stale": true}', encoding="utf-8")
    (eval_dir / "predictions.jsonl").write_text('{"stale": true}\n', encoding="utf-8")

    def interrupt_judge(predictions, *args: object, **kwargs: object):
        assert predictions
        raise KeyboardInterrupt()

    monkeypatch.setattr("rfp_rag.evaluate.JUDGED_LANES", {"offline"})
    monkeypatch.setattr("rfp_rag.judge.judge_predictions", interrupt_judge)

    with pytest.raises(KeyboardInterrupt):
        evaluate_index(
            data_path=Path("data/data_list.csv"),
            index_dir=index_dir,
            out_dir=eval_dir,
            provider="offline",
            top_k=5,
            max_docs=1,
            min_score=0.34,
        )

    unjudged = [
        json.loads(line)
        for line in (eval_dir / "predictions_unjudged.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    partial = [
        json.loads(line)
        for line in (eval_dir / "predictions_unjudged_partial.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    progress = [
        json.loads(line)
        for line in (eval_dir / "eval_progress.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert unjudged
    assert partial == unjudged
    assert (eval_dir / "contract.json").exists()
    assert (eval_dir / "golden_metadata.jsonl").exists()
    assert any(row["phase"] == "answers_complete" for row in progress)
    assert not (eval_dir / "metrics.json").exists()
    assert not (eval_dir / "predictions.jsonl").exists()


def test_call_with_retries_recovers_transient_rate_limit() -> None:
    attempts = 0

    def flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("RateLimitError: slow down")
        return "ok"

    sleeps: list[float] = []

    assert (
        _call_with_retries(
            flaky,
            max_attempts=3,
            base_delay_seconds=0.5,
            sleep=sleeps.append,
        )
        == "ok"
    )
    assert attempts == 3
    assert sleeps == [0.5, 1.0]


def test_clear_final_eval_artifacts_removes_stale_recovery_outputs(
    tmp_path: Path,
) -> None:
    for name in [
        "metrics.json",
        "predictions.jsonl",
        "predictions_unjudged.jsonl",
        "report.md",
    ]:
        (tmp_path / name).write_text("stale", encoding="utf-8")

    _clear_final_eval_artifacts(tmp_path)

    assert not (tmp_path / "metrics.json").exists()
    assert not (tmp_path / "predictions.jsonl").exists()
    assert not (tmp_path / "predictions_unjudged.jsonl").exists()
    assert not (tmp_path / "report.md").exists()


def test_evaluate_index_writes_visual_table_slice_when_reviewed_records_are_supplied(
    tmp_path: Path, parsed_manifest_factory
) -> None:
    index_dir = _build_fake_index(
        tmp_path, parsed_manifest_factory(Path("data/data_list.csv"))
    )
    visual_records_path = tmp_path / "visual" / "records.jsonl"
    visual_records_path.parent.mkdir(parents=True)
    visual_records_path.write_text(
        json.dumps(
            {
                "record_id": "doc:000:p10:requirements_table",
                "doc_id": "doc:000",
                "page": 10,
                "visual_type": "requirements_table",
                "structured_facts": [
                    {
                        "fact_id": "doc:000:p10:requirements_table:fact:000",
                        "fact_type": "visual_type_present",
                        "field": "requirements",
                        "value": "Requirements table is present on the selected page",
                    }
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    eval_dir = tmp_path / "eval"

    metrics = evaluate_index(
        data_path=Path("data/data_list.csv"),
        index_dir=index_dir,
        out_dir=eval_dir,
        provider="fake_offline",
        top_k=5,
        max_docs=1,
        min_score=0.34,
        visual_records_path=visual_records_path,
    )

    visual_questions = [
        json.loads(line)
        for line in (eval_dir / "visual_table_questions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert metrics["query_set_counts"]["visual_table"] == 1
    assert metrics["query_set_counts"]["total"] == (
        metrics["query_set_counts"]["golden_metadata"]
        + metrics["query_set_counts"]["curated_text"]
        + metrics["query_set_counts"]["section_lookup"]
        + metrics["query_set_counts"]["cross_document"]
        + metrics["query_set_counts"]["visual_table"]
        + metrics["query_set_counts"]["paraphrase"]
        + metrics["query_set_counts"]["abstention"]
    )
    assert visual_questions[0]["expected_visual_record_ids"] == [
        "doc:000:p10:requirements_table"
    ]
    assert metrics["aggregate"]["visual_evidence_hit_rate"] is not None
    assert "visual_table" in metrics["per_type"]


def test_evaluate_index_writes_hybrid_retrieval_mode_artifacts(
    tmp_path: Path, parsed_manifest_factory
) -> None:
    index_dir = _build_fake_index(
        tmp_path, parsed_manifest_factory(Path("data/data_list.csv"))
    )
    eval_dir = tmp_path / "eval"

    metrics = evaluate_index(
        data_path=Path("data/data_list.csv"),
        index_dir=index_dir,
        out_dir=eval_dir,
        provider="fake_offline",
        top_k=5,
        max_docs=3,
        min_score=0.34,
        retrieval_mode="hybrid",
    )

    assert metrics["retrieval_mode"] == "hybrid"
    saved_metrics = json.loads((eval_dir / "metrics.json").read_text(encoding="utf-8"))
    assert saved_metrics["retrieval_mode"] == "hybrid"
    assert saved_metrics == metrics
    assert (eval_dir / "predictions.jsonl").exists()
    assert (eval_dir / "report.md").exists()
    assert "- retrieval_mode: hybrid" in (eval_dir / "report.md").read_text(
        encoding="utf-8"
    )


def test_evaluate_index_rejects_unknown_retrieval_mode_before_queries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parsed_manifest_factory
) -> None:
    index_dir = _build_fake_index(
        tmp_path, parsed_manifest_factory(Path("data/data_list.csv"))
    )

    def fail_answer_query(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("answer_query should not run for invalid retrieval_mode")

    monkeypatch.setattr("rfp_rag.evaluate.answer_with_store", fail_answer_query)
    with pytest.raises(ValueError, match="unknown retrieval_mode"):
        evaluate_index(
            data_path=Path("data/data_list.csv"),
            index_dir=index_dir,
            out_dir=tmp_path / "eval",
            retrieval_mode="magic",
        )


def test_evaluate_index_rejects_offline_llm_reranker_before_queries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parsed_manifest_factory
) -> None:
    index_dir = _build_fake_index(
        tmp_path, parsed_manifest_factory(Path("data/data_list.csv"))
    )

    def fail_answer_query(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("answer_query should not run for invalid reranker lane")

    monkeypatch.setattr("rfp_rag.evaluate.answer_with_store", fail_answer_query)
    with pytest.raises(ValueError, match="LLM reranker requires real_openai or open"):
        evaluate_index(
            data_path=Path("data/data_list.csv"),
            index_dir=index_dir,
            out_dir=tmp_path / "eval",
            provider="offline",
            reranker="llm",
        )


def test_evaluate_index_preserves_reranker_metadata_on_answer_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parsed_manifest_factory
) -> None:
    index_dir = _build_fake_index(
        tmp_path, parsed_manifest_factory(Path("data/data_list.csv"))
    )
    eval_dir = tmp_path / "eval"

    class _Reranker:
        name = "llm"

    def fail_answer_query(*args: object, **kwargs: object) -> dict[str, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr("rfp_rag.evaluate.build_reranker", lambda *args: _Reranker())
    monkeypatch.setattr("rfp_rag.evaluate.answer_with_store", fail_answer_query)

    metrics = evaluate_index(
        data_path=Path("data/data_list.csv"),
        index_dir=index_dir,
        out_dir=eval_dir,
        provider="offline",
        max_docs=1,
        reranker="llm",
        rerank_candidate_k=10,
    )

    first_prediction = json.loads(
        (eval_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert metrics["reranker"] == "llm"
    assert first_prediction["reranker"] == "llm"
    assert first_prediction["rerank_candidate_k"] == 10
    assert first_prediction["reranker_scores"] == []
    assert first_prediction["warnings"] == ["answer_error:RuntimeError"]


def test_evaluate_index_labels_generation_stage_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parsed_manifest_factory
) -> None:
    index_dir = _build_fake_index(
        tmp_path, parsed_manifest_factory(Path("data/data_list.csv"))
    )
    eval_dir = tmp_path / "eval"

    def fail_generation(*args: object, **kwargs: object) -> dict[str, object]:
        raise AnswerStageError("generation", RuntimeError("RateLimitError"))

    monkeypatch.setattr("rfp_rag.evaluate.answer_with_store", fail_generation)

    evaluate_index(
        data_path=Path("data/data_list.csv"),
        index_dir=index_dir,
        out_dir=eval_dir,
        provider="offline",
        max_docs=1,
    )

    first_prediction = json.loads(
        (eval_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert first_prediction["warnings"] == ["generation_error:RuntimeError"]


def test_report_check_requires_readme_commands_and_eval_outputs(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    from rfp_rag.contracts import offline_contract

    contract = offline_contract()
    for name in contract["required_eval_files"]:
        (eval_dir / name).write_text("{}\n", encoding="utf-8")
    (eval_dir / "metrics.json").write_text(
        json.dumps(
            {
                "provider_lane": "offline",
                "offline_scaffold_complete": True,
                "rag_quality_complete": False,
                "thresholds_applied": False,
            }
        ),
        encoding="utf-8",
    )
    (eval_dir / "contract.json").write_text(
        json.dumps(contract),
        encoding="utf-8",
    )
    readme = tmp_path / "README.md"
    readme.write_text(
        "\n".join(
            [
                *contract["required_commands"],
                *contract["readme_markers"],
                "The offline lane is an offline contract gate and does not claim semantic quality.",
                "Real provider quality lane (rfp-rag-real-v5)",
            ]
        ),
        encoding="utf-8",
    )

    result = check_report(eval_dir, readme)

    assert result["ok"] is True
    assert result["missing_files"] == []
    assert result["missing_readme_snippets"] == []


def test_report_check_rejects_tampered_contract_and_missing_artifacts(
    tmp_path: Path,
) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    (eval_dir / "contract.json").write_text(
        json.dumps(
            {
                "contract_version": "not-the-current-contract",
                "required_eval_files": ["contract.json"],
                "required_commands": [],
                "readme_markers": [],
            }
        ),
        encoding="utf-8",
    )
    readme = tmp_path / "README.md"
    readme.write_text("", encoding="utf-8")

    result = check_report(eval_dir, readme)

    assert result["ok"] is False
    assert "contract_version_mismatch" in result["metric_warnings"]
    assert "metrics.json" in result["missing_files"]
    assert "python3 -m pytest" in result["missing_readme_snippets"]


def test_report_check_flags_real_lane_eval_dir_as_unsupported(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    (eval_dir / "contract.json").write_text(
        json.dumps({"contract_version": "rfp-rag-real-v5"}), encoding="utf-8"
    )
    readme = tmp_path / "README.md"
    readme.write_text("", encoding="utf-8")

    result = check_report(eval_dir, readme)

    assert result["ok"] is False
    assert "real_lane_eval_dir_not_supported" in result["metric_warnings"]
    assert "contract_version_mismatch" not in result["metric_warnings"]


# "offline" is what evaluate.py writes today (normalized lane); "fake_offline"
# proves legacy artifacts still trip the drift guards.
@pytest.mark.parametrize("lane", ["offline", "fake_offline"])
def test_report_check_rejects_offline_metric_drift(tmp_path: Path, lane: str) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    from rfp_rag.contracts import offline_contract

    contract = offline_contract()
    for name in contract["required_eval_files"]:
        (eval_dir / name).write_text("{}\n", encoding="utf-8")
    (eval_dir / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
    (eval_dir / "metrics.json").write_text(
        json.dumps(
            {
                "provider_lane": lane,
                "offline_scaffold_complete": True,
                "rag_quality_complete": True,
                "thresholds_applied": True,
            }
        ),
        encoding="utf-8",
    )
    readme = tmp_path / "README.md"
    readme.write_text(
        "\n".join(contract["required_commands"] + contract["readme_markers"]),
        encoding="utf-8",
    )

    result = check_report(eval_dir, readme)

    assert result["ok"] is False
    assert "offline_must_not_claim_rag_quality_complete" in result["metric_warnings"]
    assert "offline_must_not_apply_real_quality_thresholds" in result["metric_warnings"]
