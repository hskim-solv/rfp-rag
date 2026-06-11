from __future__ import annotations

import json
from pathlib import Path

import pytest

from rfp_rag.build_index import build_index
from rfp_rag.evaluate import evaluate_index
from rfp_rag.report_check import check_report


def test_evaluate_index_writes_offline_contract_artifacts(tmp_path: Path) -> None:
    index_dir = tmp_path / "index"
    eval_dir = tmp_path / "eval"
    build_index(
        data_path=Path("data/data_list.csv"),
        files_path=Path("data/files"),
        out_dir=index_dir,
        chunk_size=500,
        chunk_overlap=80,
        embedding_provider="fake",
    )

    metrics = evaluate_index(
        data_path=Path("data/data_list.csv"),
        index_dir=index_dir,
        out_dir=eval_dir,
        provider="fake_offline",  # legacy alias, normalized to the offline lane
        top_k=5,
        max_docs=3,
        min_score=0.15,  # calibrated offline cutoff; rationale recorded in score_distribution
    )

    assert metrics["provider_lane"] == "offline"
    assert metrics["min_score"] == 0.15
    assert metrics["evaluation_valid"] is True
    assert metrics["error_rate"] == 0.0
    assert metrics["offline_scaffold_complete"] is True
    assert metrics["rag_quality_complete"] is False
    assert metrics["thresholds_applied"] is False
    assert metrics["query_set_counts"]["abstention"] == 10
    assert metrics["score_distribution"]["abstention_top_scores"]
    assert metrics["score_distribution"]["in_domain_top_scores"]
    assert metrics["aggregate"]["citation_presence"] >= 0.95
    assert metrics["aggregate"]["citation_validity"] >= 0.90
    assert metrics["aggregate"]["abstention_pass"] >= 0.90
    for name in [
        "golden_metadata.jsonl",
        "curated_text_questions.jsonl",
        "abstention_questions.jsonl",
        "metrics.json",
        "predictions.jsonl",
        "report.md",
        "contract.json",
    ]:
        assert (eval_dir / name).exists(), name
    saved_metrics = json.loads((eval_dir / "metrics.json").read_text(encoding="utf-8"))
    contract = json.loads((eval_dir / "contract.json").read_text(encoding="utf-8"))
    assert saved_metrics == metrics
    assert contract["contract_version"] == "rfp-rag-offline-v1"
    assert contract["quality_semantics"]["offline"]["claims_semantic_quality"] is False


def test_report_check_requires_readme_commands_and_eval_outputs(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    for name in [
        "golden_metadata.jsonl",
        "curated_text_questions.jsonl",
        "abstention_questions.jsonl",
        "metrics.json",
        "predictions.jsonl",
        "report.md",
        "contract.json",
    ]:
        (eval_dir / name).write_text("{}\n", encoding="utf-8")
    (eval_dir / "metrics.json").write_text(json.dumps({"provider_lane": "offline", "offline_scaffold_complete": True, "rag_quality_complete": False, "thresholds_applied": False}), encoding="utf-8")
    (eval_dir / "contract.json").write_text(json.dumps({"contract_version": "rfp-rag-offline-v1", "required_commands": ["python3 -m pytest", "python3 -m rfp_rag.inspect_corpus --data data/data_list.csv --files data/files --out artifacts/corpus_manifest.json", "python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index --chunk-size 500 --chunk-overlap 80 --embedding-provider offline", "python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index --out artifacts/eval --provider offline --top-k 5 --min-score 0.15", "python3 -m rfp_rag.report_check --eval artifacts/eval --readme README.md"], "readme_markers": ["rfp-rag-offline-v1", "does not claim semantic quality"], "quality_semantics": {"offline": {"claims_semantic_quality": False}}}), encoding="utf-8")
    readme = tmp_path / "README.md"
    readme.write_text(
        "\n".join(
            [
                "rfp-rag-offline-v1",
                "python3 -m pytest",
                "python3 -m rfp_rag.inspect_corpus --data data/data_list.csv --files data/files --out artifacts/corpus_manifest.json",
                "python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index --chunk-size 500 --chunk-overlap 80 --embedding-provider offline",
                "python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index --out artifacts/eval --provider offline --top-k 5 --min-score 0.15",
                "python3 -m rfp_rag.report_check --eval artifacts/eval --readme README.md",
                "The offline lane is an offline contract gate and does not claim semantic quality.",
                "Real provider quality lane (rfp-rag-real-v2)",
            ]
        ),
        encoding="utf-8",
    )

    result = check_report(eval_dir, readme)

    assert result["ok"] is True
    assert result["missing_files"] == []
    assert result["missing_readme_snippets"] == []


def test_report_check_rejects_tampered_contract_and_missing_artifacts(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    (eval_dir / "contract.json").write_text(
        json.dumps({
            "contract_version": "not-the-current-contract",
            "required_eval_files": ["contract.json"],
            "required_commands": [],
            "readme_markers": [],
        }),
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
        json.dumps({"contract_version": "rfp-rag-real-v2"}), encoding="utf-8"
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
        json.dumps({
            "provider_lane": lane,
            "offline_scaffold_complete": True,
            "rag_quality_complete": True,
            "thresholds_applied": True,
        }),
        encoding="utf-8",
    )
    readme = tmp_path / "README.md"
    readme.write_text("\n".join(contract["required_commands"] + contract["readme_markers"]), encoding="utf-8")

    result = check_report(eval_dir, readme)

    assert result["ok"] is False
    assert "offline_must_not_claim_rag_quality_complete" in result["metric_warnings"]
    assert "offline_must_not_apply_real_quality_thresholds" in result["metric_warnings"]
