from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.gate_status import collect_gate_status, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
        + "\n",
        encoding="utf-8",
    )


def _records(prefix: str, count: int) -> list[dict]:
    return [{"id": f"{prefix}_{idx:03d}"} for idx in range(count)]


def _write_valid_portfolio_gates(root: Path) -> None:
    _write_jsonl(
        root / "artifacts/parsed_docs/manifest.jsonl",
        [
            {
                "doc_id": f"doc:{idx:03d}",
                "parse_status": "parsed",
                "source_quality": "source_parsed",
            }
            for idx in range(100)
        ],
    )
    _write_jsonl(
        root / "artifacts/index/chunks.jsonl",
        [{"chunk_id": f"doc:000:chunk:{idx}", "doc_id": "doc:000"} for idx in range(3)],
    )
    _write_jsonl(
        root / "artifacts/index_real/chunks.jsonl",
        [{"chunk_id": f"doc:000:chunk:{idx}", "doc_id": "doc:000"} for idx in range(3)],
    )
    _write_jsonl(root / "artifacts/eval/predictions.jsonl", _records("offline", 545))
    _write_jsonl(root / "artifacts/eval_real/predictions.jsonl", _records("real", 545))
    _write_jsonl(root / "artifacts/eval_agent/predictions.jsonl", _records("agent", 85))
    _write_jsonl(
        root / "artifacts/eval_agent/agent_artifacts/audit.jsonl",
        [
            {
                "ts": "2026-06-18T00:00:00+00:00",
                "thread_id": "eval",
                "tool": "search_rfp",
                "args": {"query": "q", "top_k": 5},
                "outcome": "1 result",
                "approved": None,
            },
            {
                "ts": "2026-06-18T00:00:01+00:00",
                "thread_id": "eval",
                "tool": "aggregate_metadata",
                "args": {},
                "outcome": "ok",
                "approved": None,
            },
        ],
    )
    _write_json(
        root / "artifacts/index/manifest.json",
        {
            "chunk_count": 3,
            "embedding_provider": "offline",
            "index_text_source_counts": {"parsed": 100},
            "parse_manifest_path": "artifacts/parsed_docs/manifest.jsonl",
            "text_source": "parsed",
            "unique_docs": 100,
        },
    )
    _write_json(
        root / "artifacts/index_real/manifest.json",
        {
            "chunk_count": 3,
            "embedding_provider": "real_openai",
            "index_text_source_counts": {"parsed": 100},
            "parse_manifest_path": "artifacts/parsed_docs/manifest.jsonl",
            "text_source": "parsed",
            "unique_docs": 100,
        },
    )
    _write_json(
        root / "artifacts/eval/contract.json",
        {
            "contract_version": "rfp-rag-offline-v4",
            "required_commands": [
                "python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index --out artifacts/eval --provider offline --top-k 5 --min-score 0.34 --visual-records artifacts/visual_structure_reviewed/records.jsonl",
            ],
        },
    )
    _write_json(
        root / "artifacts/eval_real/contract.json",
        {
            "contract_version": "rfp-rag-real-v6",
            "required_commands": [
                "python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index_real --chunk-size 500 --chunk-overlap 80 --embedding-provider openai --parse-manifest artifacts/parsed_docs/manifest.jsonl",
                "python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_real --out artifacts/eval_real --provider real_openai --top-k 5 --min-score 0.47 --visual-records artifacts/visual_structure_reviewed/records.jsonl",
            ],
        },
    )
    _write_json(
        root / "artifacts/eval_agent/contract.json",
        {
            "contract_version": "rfp-agent-v2",
            "required_commands": [
                "python3 -m rfp_rag.agent.evaluate_agent --data data/data_list.csv --files data/files --index artifacts/index --out artifacts/eval_agent --provider offline --top-k 5 --min-score 0.34",
            ],
        },
    )
    _write_json(
        root / "artifacts/eval/metrics.json",
        {
            "evaluation_valid": True,
            "min_score": 0.34,
            "offline_scaffold_complete": True,
            "provider_lane": "offline",
            "query_set_counts": {
                "abstention": 30,
                "cross_document": 20,
                "curated_text": 10,
                "golden_metadata": 400,
                "paraphrase": 30,
                "section_lookup": 30,
                "visual_table": 25,
                "total": 545,
            },
            "rag_quality_complete": False,
            "reranker": "none",
            "retrieval_mode": "vector",
            "thresholds_met": False,
            "top_k": 5,
        },
    )
    _write_json(
        root / "artifacts/eval_real/metrics.json",
        {
            "evaluation_valid": True,
            "min_score": 0.47,
            "offline_scaffold_complete": True,
            "provider_lane": "real_openai",
            "query_set_counts": {
                "abstention": 30,
                "cross_document": 20,
                "curated_text": 10,
                "golden_metadata": 400,
                "paraphrase": 30,
                "section_lookup": 30,
                "visual_table": 25,
                "total": 545,
            },
            "rag_quality_complete": True,
            "reranker": "none",
            "retrieval_mode": "vector",
            "thresholds_met": True,
            "top_k": 5,
            "generation_model_id": "gpt-5.4-mini",
            "judge_model_id": "gpt-5.4-mini",
            "embedding_model_id": "text-embedding-3-small",
            "prompt_template_hash": "a" * 64,
            "per_type": {
                "cross_document": {
                    "recall@5": 0.90,
                    "all_expected_docs_retrieved@5": 0.90,
                },
                "section_lookup": {"section_hit_rate": 1.0},
                "visual_table": {"visual_evidence_hit_rate": 1.0},
            },
        },
    )
    _write_json(
        root / "artifacts/eval_agent/metrics.json",
        {
            "agent_lane_complete": True,
            "counts": {
                "abstention": 30,
                "regression": 20,
                "rewrite": 5,
                "routing": 20,
                "tool": 10,
            },
            "gate": {
                "agent_lane_complete": True,
                "evaluation_valid": True,
                "failed": [],
                "thresholds_applied": True,
            },
            "lane": "offline",
            "min_score": 0.34,
            "top_k": 5,
            "audit_line_count": 2,
            "audit_tool_counts": {"aggregate_metadata": 1, "search_rfp": 1},
        },
    )
    _write_json(
        root / "artifacts/visual_tesseract_candidate_expanded_gate/summary.json",
        {
            "decision": "visual_candidate_gate",
            "failures": [],
            "metrics": {
                "candidate_fact_count": 26,
                "f1": 0.78,
                "negative_violation_count": 3,
                "precision": 0.77,
                "recall": 0.8,
            },
            "ok": True,
            "thresholds": {
                "max_negative_violation_count": 3,
                "min_f1": 0.7,
                "min_precision": 0.7,
                "min_recall": 0.7,
            },
        },
    )


def _issue_codes(lane: dict) -> set[str]:
    return {issue["code"] for issue in lane.get("issues", [])}


def test_collect_gate_status_validates_fresh_portfolio_artifacts(
    tmp_path: Path,
) -> None:
    _write_valid_portfolio_gates(tmp_path)

    status = collect_gate_status(tmp_path)

    assert status["overall_ok"] is True
    assert status["lanes"]["offline_rag"]["value"] is True
    assert status["lanes"]["offline_rag"]["contract_version"] == "rfp-rag-offline-v4"
    assert status["lanes"]["real_rag"]["value"] is True
    assert status["lanes"]["agent_offline"]["failed"] == []
    assert status["lanes"]["visual_candidate"]["path"] == (
        "artifacts/visual_tesseract_candidate_expanded_gate/summary.json"
    )
    assert all(not lane["issues"] for lane in status["lanes"].values())


def test_collect_gate_status_fails_real_cross_document_blind_spot(
    tmp_path: Path,
) -> None:
    _write_valid_portfolio_gates(tmp_path)
    metrics = json.loads(
        (tmp_path / "artifacts/eval_real/metrics.json").read_text(encoding="utf-8")
    )
    metrics["per_type"]["cross_document"] = {
        "recall@5": 0.65,
        "all_expected_docs_retrieved@5": 0.30,
    }
    _write_json(tmp_path / "artifacts/eval_real/metrics.json", metrics)

    status = collect_gate_status(tmp_path)

    assert status["overall_ok"] is False
    assert "per_type_threshold_mismatch" in _issue_codes(status["lanes"]["real_rag"])


def test_collect_gate_status_requires_agent_audit_artifact(tmp_path: Path) -> None:
    _write_valid_portfolio_gates(tmp_path)
    (tmp_path / "artifacts/eval_agent/agent_artifacts/audit.jsonl").unlink()

    status = collect_gate_status(tmp_path)

    assert status["overall_ok"] is False
    assert "audit_missing" in _issue_codes(status["lanes"]["agent_offline"])


def test_collect_gate_status_fails_stale_real_source_evidence(
    tmp_path: Path,
) -> None:
    _write_valid_portfolio_gates(tmp_path)
    _write_json(
        tmp_path / "artifacts/index_real/manifest.json",
        {
            "chunk_count": 286,
            "embedding_provider": "real_openai",
            "unique_docs": 100,
        },
    )
    _write_json(
        tmp_path / "artifacts/eval_real/contract.json",
        {
            "contract_version": "rfp-rag-real-v2",
            "required_commands": [
                "python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index_real --chunk-size 500 --chunk-overlap 80 --embedding-provider openai",
                "python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_real --out artifacts/eval_real --provider real_openai --top-k 5 --min-score 0.47",
            ],
        },
    )
    _write_json(
        tmp_path / "artifacts/eval_real/metrics.json",
        {
            "evaluation_valid": True,
            "min_score": 0.47,
            "provider_lane": "real_openai",
            "query_set_counts": {
                "abstention": 10,
                "curated_text": 10,
                "golden_metadata": 40,
                "total": 60,
            },
            "rag_quality_complete": True,
            "reaggregated_from_predictions": True,
            "thresholds_met": True,
            "top_k": 5,
        },
    )

    status = collect_gate_status(tmp_path)

    assert status["overall_ok"] is False
    assert status["lanes"]["real_rag"]["ok"] is False
    assert _issue_codes(status["lanes"]["real_rag"]) >= {
        "contract_version_mismatch",
        "index_parse_manifest_mismatch",
        "index_text_source_mismatch",
        "query_set_counts_mismatch",
        "reranker_mismatch",
        "retrieval_mode_mismatch",
    }
    assert status["lanes"]["real_rag"]["reaggregated_from_predictions"] is True


def test_collect_gate_status_fails_stale_agent_policy(tmp_path: Path) -> None:
    _write_valid_portfolio_gates(tmp_path)
    _write_json(
        tmp_path / "artifacts/eval_agent/contract.json",
        {
            "contract_version": "rfp-agent-v1",
            "required_commands": [
                "python3 -m rfp_rag.agent.evaluate_agent --data data/data_list.csv --files data/files --index artifacts/index --out artifacts/eval_agent --provider offline --top-k 5 --min-score 0.15",
            ],
        },
    )
    _write_json(
        tmp_path / "artifacts/eval_agent/metrics.json",
        {
            "agent_lane_complete": True,
            "counts": {
                "abstention": 10,
                "regression": 20,
                "rewrite": 5,
                "routing": 20,
                "tool": 10,
            },
            "gate": {
                "agent_lane_complete": True,
                "evaluation_valid": True,
                "failed": [],
                "thresholds_applied": True,
            },
            "lane": "offline",
            "min_score": 0.15,
            "top_k": 5,
        },
    )

    status = collect_gate_status(tmp_path)

    assert status["overall_ok"] is False
    assert status["lanes"]["agent_offline"]["ok"] is False
    assert _issue_codes(status["lanes"]["agent_offline"]) >= {
        "min_score_mismatch",
        "required_command_mismatch",
    }


def test_collect_gate_status_requires_lineage_files_and_counts(
    tmp_path: Path,
) -> None:
    _write_valid_portfolio_gates(tmp_path)
    (tmp_path / "artifacts/parsed_docs/manifest.jsonl").unlink()
    _write_jsonl(
        tmp_path / "artifacts/index/chunks.jsonl",
        [{"chunk_id": "doc:000:chunk:0", "doc_id": "doc:000"}],
    )
    _write_jsonl(tmp_path / "artifacts/eval/predictions.jsonl", _records("short", 69))

    status = collect_gate_status(tmp_path)

    assert status["overall_ok"] is False
    assert status["lanes"]["offline_rag"]["ok"] is False
    assert _issue_codes(status["lanes"]["offline_rag"]) >= {
        "chunks_line_count_mismatch",
        "parse_manifest_missing",
        "predictions_line_count_mismatch",
    }


def test_collect_gate_status_reports_malformed_schema_without_raising(
    tmp_path: Path,
) -> None:
    _write_valid_portfolio_gates(tmp_path)
    manifest = json.loads(
        (tmp_path / "artifacts/index/manifest.json").read_text(encoding="utf-8")
    )
    manifest["index_text_source_counts"] = None
    _write_json(tmp_path / "artifacts/index/manifest.json", manifest)

    status = collect_gate_status(tmp_path)

    assert status["overall_ok"] is False
    assert status["lanes"]["offline_rag"]["ok"] is False
    assert "index_text_source_counts_mismatch" in _issue_codes(
        status["lanes"]["offline_rag"]
    )


def test_collect_gate_status_reports_missing_without_raising(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "artifacts/eval/metrics.json",
        {"offline_scaffold_complete": True},
    )

    status = collect_gate_status(tmp_path)

    assert status["overall_ok"] is False
    assert status["lanes"]["offline_rag"]["present"] is True
    assert status["lanes"]["real_rag"] == {
        "gate_key": "rag_quality_complete",
        "issues": [],
        "ok": False,
        "path": "artifacts/eval_real/metrics.json",
        "present": False,
        "value": None,
    }


def test_gate_status_main_prints_json(capsys, tmp_path: Path) -> None:
    _write_json(
        tmp_path / "artifacts/eval/metrics.json",
        {"offline_scaffold_complete": True},
    )

    rc = main(["--root", str(tmp_path)])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["overall_ok"] is False
    assert payload["lanes"]["agent_offline"]["present"] is False
