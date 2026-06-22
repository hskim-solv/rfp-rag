from __future__ import annotations

import json
from pathlib import Path

import pytest

from rfp_rag.contracts import REAL_CONTRACT_VERSION
from rfp_rag.evaluate import main, reaggregate_metrics


def _prediction(
    query_id: str,
    query_type: str = "curated_text",
    judge: dict | None = None,
) -> dict:
    return {
        "query_id": query_id,
        "query": "사업 요약해줘",
        "query_type": query_type,
        "expected_doc_ids": ["doc:000"],
        "retrieved_doc_ids": ["doc:000"],
        "retrieved_chunk_ids": ["doc:000:chunk:0"],
        "answer": "본 사업은 학사정보시스템 고도화이다.",
        "sources": [{"chunk_id": "doc:000:chunk:0", "doc_id": "doc:000"}],
        "source_texts": ["학사정보시스템 고도화 사업 본문"],
        "warnings": [],
        "scores": [0.9],
        "pass_fail": {
            "recall@3": 1.0,
            "recall@5": 1.0,
            "mrr": 1.0,
            "citation_presence": 1.0,
            "citation_validity": 1.0,
            "metadata_exact_match": 1.0,
            "abstention_pass": None,
        },
        "judge": judge
        or {"faithfulness": 0.9, "answer_relevancy": 0.85, "warnings": []},
    }


def _uncited_prediction(query_id: str) -> dict:
    pred = _prediction(query_id)
    pred["sources"] = []
    pred["source_texts"] = []
    pred["pass_fail"]["citation_presence"] = 0.0
    pred["pass_fail"]["citation_validity"] = 0.0
    return pred


def _abstention_prediction(query_id: str) -> dict:
    pred = _prediction(query_id, query_type="abstention")
    pred["pass_fail"] = {
        "recall@3": None,
        "recall@5": None,
        "mrr": None,
        "citation_presence": None,
        "citation_validity": None,
        "metadata_exact_match": None,
        "abstention_pass": 1.0,
    }
    pred["sources"] = []
    pred["judge"] = {
        "faithfulness": None,
        "answer_relevancy": None,
        "warnings": ["judge_skipped_abstention"],
    }
    return pred


def _cross_document_prediction(query_id: str) -> dict:
    pred = _prediction(query_id, query_type="cross_document")
    pred["expected_doc_ids"] = ["doc:000", "doc:001"]
    pred["retrieved_doc_ids"] = ["doc:000", "doc:001"]
    pred["pass_fail"]["all_expected_docs_retrieved@5"] = 1.0
    return pred


def _section_lookup_prediction(query_id: str) -> dict:
    pred = _prediction(query_id, query_type="section_lookup")
    pred["pass_fail"]["section_hit_rate"] = 1.0
    return pred


def _visual_table_prediction(query_id: str) -> dict:
    pred = _prediction(query_id, query_type="visual_table")
    pred["pass_fail"]["visual_evidence_hit_rate"] = 1.0
    return pred


def _unjudged_answer_prediction(query_id: str, query_type: str) -> dict:
    pred = _prediction(query_id, query_type=query_type)
    pred["judge"] = {
        "faithfulness": None,
        "answer_relevancy": None,
        "warnings": ["judge_aborted"],
    }
    if query_type == "cross_document":
        pred["expected_doc_ids"] = ["doc:000", "doc:001"]
        pred["retrieved_doc_ids"] = ["doc:000", "doc:001"]
        pred["pass_fail"]["all_expected_docs_retrieved@5"] = 1.0
    elif query_type == "section_lookup":
        pred["pass_fail"]["section_hit_rate"] = 1.0
    elif query_type == "visual_table":
        pred["pass_fail"]["visual_evidence_hit_rate"] = 1.0
    return pred


def _write_eval_dir(tmp_path: Path, predictions: list[dict]) -> Path:
    eval_dir = tmp_path / "eval_real"
    eval_dir.mkdir()
    with (eval_dir / "predictions.jsonl").open("w", encoding="utf-8") as f:
        for pred in predictions:
            f.write(json.dumps(pred, ensure_ascii=False) + "\n")
    # 이전 run의 metrics — predictions에서 도출 불가한 실행 파라미터의 출처.
    (eval_dir / "metrics.json").write_text(
        json.dumps(
            {
                "provider_lane": "real_openai",
                "eval_set_hash": "eval-set-hash",
                "top_k": 5,
                "min_score": 0.47,
                "query_set_counts": {
                    "golden_metadata": 10,
                    "curated_text": 10,
                    "cross_document": 1,
                    "section_lookup": 1,
                    "visual_table": 1,
                    "abstention": 1,
                    "total": len(predictions),
                },
            }
        ),
        encoding="utf-8",
    )
    return eval_dir


def test_reaggregate_recomputes_coverage_and_gates_without_api_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # RAG/judge를 다시 호출하면 즉시 실패 — 재집계는 기존 산출물만 읽어야 한다.
    import rfp_rag.rag_chain as rag_chain

    monkeypatch.setattr(
        rag_chain,
        "answer_query",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("RAG call")),
    )
    preds = [_prediction(f"q{i}") for i in range(10)] + [
        _cross_document_prediction("cross_0"),
        _section_lookup_prediction("section_0"),
        _visual_table_prediction("visual_0"),
        _abstention_prediction("abst_0"),
    ]
    eval_dir = _write_eval_dir(tmp_path, preds)

    metrics = reaggregate_metrics(eval_dir, provider="real_openai")

    assert metrics["aggregate"]["judge_coverage_faithfulness"] == 1.0
    assert metrics["aggregate"]["judge_coverage_answer_relevancy"] == 1.0
    assert metrics["rag_quality_complete"] is True
    assert metrics["reaggregated_from_predictions"] is True
    assert metrics["eval_set_hash"] == "eval-set-hash"
    # 실행 파라미터는 이전 metrics에서 보존
    assert metrics["top_k"] == 5
    assert metrics["min_score"] == 0.47


def test_reaggregate_writes_current_contract_and_report(tmp_path: Path) -> None:
    eval_dir = _write_eval_dir(tmp_path, [_prediction("q0")])

    reaggregate_metrics(eval_dir, provider="real_openai")

    contract = json.loads((eval_dir / "contract.json").read_text(encoding="utf-8"))
    assert contract["contract_version"] == REAL_CONTRACT_VERSION
    written = json.loads((eval_dir / "metrics.json").read_text(encoding="utf-8"))
    assert written["reaggregated_from_predictions"] is True
    assert (eval_dir / "report.md").exists()


def test_reaggregate_fails_gate_when_coverage_low(tmp_path: Path) -> None:
    # judge 산출물이 비어 있으면(미채점) coverage 게이트가 통과를 막아야 한다
    unscored = {
        "faithfulness": None,
        "answer_relevancy": None,
        "warnings": ["judge_aborted"],
    }
    preds = [_prediction("q0")] + [
        _prediction(f"q{i}", judge=dict(unscored)) for i in range(1, 10)
    ]
    eval_dir = _write_eval_dir(tmp_path, preds)

    metrics = reaggregate_metrics(eval_dir, provider="real_openai")

    assert metrics["aggregate"]["judge_coverage_faithfulness"] == pytest.approx(0.1)
    assert metrics["rag_quality_complete"] is False


def test_reaggregate_fails_gate_when_any_non_abstention_answer_is_uncited(
    tmp_path: Path,
) -> None:
    preds = [_prediction(f"q{i}") for i in range(10)] + [
        _uncited_prediction("uncited"),
        _cross_document_prediction("cross_0"),
        _section_lookup_prediction("section_0"),
        _visual_table_prediction("visual_0"),
        _abstention_prediction("abst_0"),
    ]
    eval_dir = _write_eval_dir(tmp_path, preds)

    metrics = reaggregate_metrics(eval_dir, provider="real_openai")

    assert metrics["aggregate"]["uncited_non_abstention_count"] == 1
    assert metrics["rag_quality_complete"] is False


def test_reaggregate_requires_judge_coverage_for_answer_bearing_slices(
    tmp_path: Path,
) -> None:
    preds = [_prediction(f"q{i}") for i in range(10)] + [
        _unjudged_answer_prediction("cross_0", "cross_document"),
        _unjudged_answer_prediction("section_0", "section_lookup"),
        _unjudged_answer_prediction("visual_0", "visual_table"),
        _abstention_prediction("abst_0"),
    ]
    eval_dir = _write_eval_dir(tmp_path, preds)

    metrics = reaggregate_metrics(eval_dir, provider="real_openai")

    assert metrics["aggregate"]["judge_coverage_faithfulness"] < 1.0
    assert metrics["rag_quality_complete"] is False


def test_reaggregate_defaults_to_previous_lane(tmp_path: Path) -> None:
    # --provider 미지정 시 fake_offline 기본값이 들어가면 real 증거가 offline 계약으로
    # 덮어써진다 (PR #7 Codex P2) — 이전 run의 lane을 보존해야 한다
    eval_dir = _write_eval_dir(tmp_path, [_prediction("q0")])

    metrics = reaggregate_metrics(eval_dir)

    assert metrics["provider_lane"] == "real_openai"
    assert "judge_coverage_faithfulness" in metrics["aggregate"]
    contract = json.loads((eval_dir / "contract.json").read_text(encoding="utf-8"))
    assert contract["contract_version"] == REAL_CONTRACT_VERSION


def test_reaggregate_rejects_lane_mismatch(tmp_path: Path) -> None:
    # lane을 바꿔 재집계하면 증거 파괴 — 명시 오버라이드도 차단한다
    eval_dir = _write_eval_dir(tmp_path, [_prediction("q0")])

    with pytest.raises(ValueError, match="lane"):
        reaggregate_metrics(eval_dir, provider="offline")


def test_cli_reaggregate_without_provider_preserves_lane(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    eval_dir = _write_eval_dir(tmp_path, [_prediction("q0")])

    exit_code = main(["--reaggregate", "--out", str(eval_dir)])

    assert exit_code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["provider_lane"] == "real_openai"


def test_cli_reaggregate_runs_without_data_and_index(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    eval_dir = _write_eval_dir(tmp_path, [_prediction("q0")])

    exit_code = main(
        ["--reaggregate", "--out", str(eval_dir), "--provider", "real_openai"]
    )

    assert exit_code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["reaggregated_from_predictions"] is True


def test_cli_still_requires_data_and_index_for_full_run(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--out", str(tmp_path / "out")])

    assert excinfo.value.code != 0
