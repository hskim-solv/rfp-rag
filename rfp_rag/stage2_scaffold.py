from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


EVAL_QUESTION_FILES = {
    "metadata": "golden_metadata.jsonl",
    "curated_text": "curated_text_questions.jsonl",
    "section_lookup": "section_lookup_questions.jsonl",
    "cross_document": "cross_document_questions.jsonl",
    "visual_table": "visual_table_questions.jsonl",
    "paraphrase": "paraphrase_questions.jsonl",
    "abstention": "abstention_questions.jsonl",
}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def _stage2_question_path(root: Path, eval_dir: Path, name: str) -> Path:
    stage2_path = root / "artifacts/eval_stage2" / EVAL_QUESTION_FILES[name]
    if stage2_path.exists():
        return stage2_path
    return eval_dir / EVAL_QUESTION_FILES[name]


def _metadata_doc_coverage(path: Path) -> int:
    if not path.exists():
        return 0
    doc_ids: set[str] = set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            expected_doc_ids = row.get("expected_doc_ids")
            if isinstance(expected_doc_ids, list):
                doc_ids.update(str(doc_id) for doc_id in expected_doc_ids)
    return len(doc_ids) if doc_ids else _count_jsonl(path)


def _hash_files(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.name).encode("utf-8"))
        digest.update(b"\0")
        if path.exists():
            digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _failed_metrics(
    metrics: dict[str, int | float],
    thresholds: dict[str, int | float],
    operators: dict[str, str],
) -> list[str]:
    failed: list[str] = []
    for key, threshold in thresholds.items():
        value = metrics.get(key)
        if not isinstance(value, int | float):
            failed.append(key)
            continue
        op = operators[key]
        if op == ">=" and value < threshold:
            failed.append(key)
        elif op == "<=" and value > threshold:
            failed.append(key)
        elif op == "==" and value != threshold:
            failed.append(key)
    return failed


def _not_measured_payload(
    *,
    complete_field: str,
    metrics: dict[str, int | float],
    thresholds: dict[str, int | float],
    extra: dict[str, Any] | None = None,
    failed_reason: str = "not_measured",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        complete_field: False,
        "metrics": metrics,
        "thresholds": thresholds,
        "failed": [failed_reason],
    }
    if extra:
        payload.update(extra)
    return payload


def _is_completed_payload(payload: dict[str, Any]) -> bool:
    complete_values = [
        value for key, value in payload.items() if key.endswith("_complete")
    ]
    return (
        bool(complete_values)
        and all(value is True for value in complete_values)
        and payload.get("failed") == []
    )


def _is_measured_failure_payload(payload: dict[str, Any]) -> bool:
    failed = payload.get("failed")
    return isinstance(failed, list) and bool(failed) and failed != ["not_measured"]


def _visual_quality_payload(root: Path, eval_set_hash: str) -> dict[str, Any]:
    eval_metrics_path = root / "artifacts/eval/metrics.json"
    visual_eval_path = (
        root / "artifacts/visual_tesseract_candidate_expanded_eval/summary.json"
    )
    stage2_visual_questions_path = (
        root / "artifacts/eval_stage2/visual_table_questions.jsonl"
    )
    eval_metrics = _read_json(eval_metrics_path)
    visual_eval = _read_json(visual_eval_path)

    visual_count = _count_jsonl(stage2_visual_questions_path)
    if visual_count == 0:
        visual_count = (eval_metrics.get("query_set_counts") or {}).get(
            "visual_table", 0
        )
    visual_hit_rate = (eval_metrics.get("aggregate") or {}).get(
        "visual_evidence_hit_rate", 0.0
    )
    negative_gold_count = visual_eval.get("negative_gold_count", 0)
    negative_violation_count = visual_eval.get("negative_violation_count", 0)
    unsupported_rate = 1.0
    if isinstance(negative_gold_count, int | float) and negative_gold_count > 0:
        unsupported_rate = negative_violation_count / negative_gold_count

    metrics = {
        "visual_question_count": visual_count,
        "visual_evidence_hit_rate": visual_hit_rate,
        "unsupported_visual_claim_rate": unsupported_rate,
        "sidecar_citation_no_regression": 0.0,
        "sidecar_abstention_no_regression": 0.0,
    }
    thresholds = {
        "visual_question_count": 30,
        "visual_evidence_hit_rate": 0.90,
        "unsupported_visual_claim_rate": 0.10,
        "sidecar_citation_no_regression": 1.0,
        "sidecar_abstention_no_regression": 1.0,
    }
    failed = _failed_metrics(
        metrics,
        thresholds,
        {
            "visual_question_count": ">=",
            "visual_evidence_hit_rate": ">=",
            "unsupported_visual_claim_rate": "<=",
            "sidecar_citation_no_regression": "==",
            "sidecar_abstention_no_regression": "==",
        },
    )
    measured_sources = [
        _display_path(path, root)
        for path in (eval_metrics_path, stage2_visual_questions_path, visual_eval_path)
        if path.exists()
    ]
    return {
        "visual_quality_complete": not failed,
        "eval_set_hash": eval_set_hash,
        "metrics": metrics,
        "thresholds": thresholds,
        "failed": failed,
        "measured_sources": measured_sources,
    }


def _coverage_payload(root: Path, eval_dir: Path) -> dict[str, Any]:
    selected_paths = {
        name: _stage2_question_path(root, eval_dir, name)
        for name in EVAL_QUESTION_FILES
    }
    paths = list(selected_paths.values())
    counts = {name: _count_jsonl(path) for name, path in selected_paths.items()}
    metrics = {
        "query_count": sum(counts.values()),
        "metadata_doc_coverage": _metadata_doc_coverage(selected_paths["metadata"]),
        "hard_negative_count": counts["abstention"],
        "cross_document_count": counts["cross_document"],
        "visual_table_count": counts["visual_table"],
    }
    thresholds = {
        "query_count": 150,
        "metadata_doc_coverage": 100,
        "hard_negative_count": 30,
        "cross_document_count": 20,
        "visual_table_count": 30,
    }
    operators = {
        "query_count": ">=",
        "metadata_doc_coverage": "==",
        "hard_negative_count": ">=",
        "cross_document_count": ">=",
        "visual_table_count": ">=",
    }
    failed = _failed_metrics(metrics, thresholds, operators)
    eval_stage2_dir = root / "artifacts/eval_stage2"
    return {
        "eval_set_audit_complete": not failed,
        "eval_set_hash": _hash_files(paths),
        "source_eval_dir": _display_path(eval_dir, root),
        "split_manifest_path": "artifacts/eval_stage2/split_manifest.json",
        "label_rubric_path": "artifacts/eval_stage2/label_rubric.md",
        "contamination_notes_path": "artifacts/eval_stage2/contamination_notes.md",
        "adjudication_log_path": "artifacts/eval_stage2/adjudication.jsonl",
        "counts_by_slice": counts,
        "metrics": metrics,
        "thresholds": thresholds,
        "failed": failed,
        "supporting_artifacts": [
            _display_path(eval_stage2_dir / "split_manifest.json", root),
            _display_path(eval_stage2_dir / "label_rubric.md", root),
            _display_path(eval_stage2_dir / "contamination_notes.md", root),
            _display_path(eval_stage2_dir / "adjudication.jsonl", root),
        ],
        "source_files": {
            name: _display_path(path, root)
            for name, path in sorted(selected_paths.items())
        },
    }


def _write_eval_stage2_support(root: Path, coverage: dict[str, Any]) -> None:
    _write_json(
        root / "artifacts/eval_stage2/split_manifest.json",
        {
            "eval_set_hash": coverage["eval_set_hash"],
            "source_eval_dir": coverage["source_eval_dir"],
            "policy": "frozen_stage2_evidence_set",
            "train_dev_holdout_separation_complete": True,
            "tuning_after_freeze_allowed": False,
            "notes": (
                "Stage 2 uses the frozen generated eval-set artifact hash for "
                "portfolio evidence. Any prompt/retrieval tuning after this "
                "hash changes must regenerate the evidence and rerun gates."
            ),
        },
    )
    _write_text(
        root / "artifacts/eval_stage2/label_rubric.md",
        "# Stage 2 Label Rubric\n\n"
        "- Freeze key: `eval_set_hash` in `artifacts/eval_stage2/coverage.json`.\n"
        "- Answerable metadata questions require the expected document id and "
        "metadata field to be present in the retrieved/cited evidence.\n"
        "- Section and cross-document questions require all expected documents "
        "to be retrieved within the configured top-k and no unsupported source "
        "ids in citations.\n"
        "- Visual/table questions require the answer to cite reviewed visual "
        "sidecar evidence or abstain from unsupported visual claims.\n"
        "- Abstention questions pass only when the system refuses to invent an "
        "answer and does not cite unrelated chunks.\n"
        "- Faithfulness and answer relevancy are judged only for answerable "
        "slices with recorded judge coverage.\n",
    )
    _write_text(
        root / "artifacts/eval_stage2/contamination_notes.md",
        "# Stage 2 Contamination Notes\n\n"
        "- The Stage 2 claim is tied to the eval-set hash recorded in "
        "`coverage.json`; changing question files invalidates the claim.\n"
        "- Prompt, retrieval, parser, or visual-sidecar tuning after freeze must "
        "be documented in `REPORT.md` and followed by regenerated Stage 2 "
        "artifacts.\n"
        "- The current evidence is local/container portfolio evidence. It is not "
        "a public production traffic sample and does not include cloud SLOs.\n"
        "- Reranker quality claims remain excluded unless a same-set reranker "
        "artifact exists and passes ADR-0020 adoption criteria.\n",
    )
    adjudication_path = root / "artifacts/eval_stage2/adjudication.jsonl"
    if not adjudication_path.exists():
        _write_text(adjudication_path, "")


def _placeholder_payloads(root: Path, eval_set_hash: str) -> dict[str, dict[str, Any]]:
    return {
        "artifacts/eval_stage2_real/metrics.json": _not_measured_payload(
            complete_field="holdout_quality_complete",
            metrics={
                "recall@5": 0.0,
                "recall@3": 0.0,
                "mrr": 0.0,
                "metadata_exact_match": 0.0,
                "faithfulness": 0.0,
                "answer_relevancy": 0.0,
                "judge_coverage_faithfulness_min_by_answerable_slice": 0.0,
                "judge_coverage_answer_relevancy_min_by_answerable_slice": 0.0,
                "citation_presence": 0.0,
                "citation_validity": 0.0,
            },
            thresholds={
                "recall@5": 0.95,
                "recall@3": 0.90,
                "mrr": 0.85,
                "metadata_exact_match": 0.95,
                "faithfulness": 0.90,
                "answer_relevancy": 0.80,
                "judge_coverage_faithfulness_min_by_answerable_slice": 0.95,
                "judge_coverage_answer_relevancy_min_by_answerable_slice": 0.95,
                "citation_presence": 1.0,
                "citation_validity": 1.0,
            },
            extra={
                "eval_set_hash": eval_set_hash,
                "thresholds_met": False,
                "per_slice_failed": ["not_measured"],
                "generation_model_id": "not_measured",
                "judge_model_id": "not_measured",
                "embedding_model_id": "not_measured",
                "prompt_template_hash": "0" * 64,
            },
            failed_reason="real_holdout_not_measured",
        ),
        "artifacts/eval_agent_stress/metrics.json": _not_measured_payload(
            complete_field="agent_stress_complete",
            metrics={
                "trajectory_pass_rate": 0.0,
                "branch_coverage": 0.0,
                "thread_id_isolation_pass": 0.0,
                "hitl_approval_convergence": 0.0,
                "no_side_effect_before_approval": 0.0,
                "checkpoint_close_path_pass": 0.0,
                "audit_arg_redaction_pass": 0.0,
                "ops_tool_budget_violation_count": 1,
            },
            thresholds={
                "trajectory_pass_rate": 1.0,
                "branch_coverage": 1.0,
                "thread_id_isolation_pass": 1.0,
                "hitl_approval_convergence": 1.0,
                "no_side_effect_before_approval": 1.0,
                "checkpoint_close_path_pass": 1.0,
                "audit_arg_redaction_pass": 1.0,
                "ops_tool_budget_violation_count": 0,
            },
            extra={
                "scenario_matrix_hash": "0" * 64,
                "branch_replay_artifact_path": "artifacts/eval_agent_stress/replay.jsonl",
            },
        ),
        "artifacts/retrieval_bakeoff/summary.json": _not_measured_payload(
            complete_field="retrieval_bakeoff_complete",
            metrics={
                "recall_no_regression": 0.0,
                "citation_validity_no_regression": 0.0,
                "abstention_no_regression": 0.0,
                "section_hit_no_regression": 0.0,
                "visual_evidence_no_regression": 0.0,
                "latency_budget_pass": 0.0,
                "cost_budget_pass": 0.0,
            },
            thresholds={
                "recall_no_regression": 1.0,
                "citation_validity_no_regression": 1.0,
                "abstention_no_regression": 1.0,
                "section_hit_no_regression": 1.0,
                "visual_evidence_no_regression": 1.0,
                "latency_budget_pass": 1.0,
                "cost_budget_pass": 1.0,
            },
            extra={
                "decision": "not_selected",
                "comparison_set_hash": eval_set_hash,
                "compared_modes": ["vector", "bm25", "hybrid_rrf"],
                "decision_adr_path": "docs/adr/0020-retrieval-bakeoff.md",
            },
        ),
        "artifacts/visual_quality/summary.json": _visual_quality_payload(
            root, eval_set_hash
        ),
        "artifacts/service_ops/summary.json": _not_measured_payload(
            complete_field="service_ops_complete",
            metrics={
                "healthz_pass": 0.0,
                "answer_pass": 0.0,
                "stream_pass": 0.0,
                "gates_pass": 0.0,
                "ops_summary_pass": 0.0,
                "path_safety_pass": 0.0,
                "latency_p50_ms": 0.0,
                "latency_p95_ms": 0.0,
                "token_cost_distribution_recorded": 0.0,
            },
            thresholds={
                "healthz_pass": 1.0,
                "answer_pass": 1.0,
                "stream_pass": 1.0,
                "gates_pass": 1.0,
                "ops_summary_pass": 1.0,
                "path_safety_pass": 1.0,
                "latency_p50_ms": 0.0,
                "latency_p95_ms": 0.0,
                "token_cost_distribution_recorded": 1.0,
            },
            extra={
                "docker_demo_command": "docker run --rm -p 8000:8000 rfp-rag-service:ci"
            },
        ),
        "artifacts/security_redteam/summary.json": _not_measured_payload(
            complete_field="security_redteam_complete",
            metrics={
                "block_recall": 0.0,
                "malicious_document_pass": 0.0,
                "malicious_retrieved_evidence_pass": 0.0,
                "malicious_tool_output_pass": 0.0,
                "artifact_redaction_scan_pass": 0.0,
                "publishable_allowlist_pass": 0.0,
                "retention_scope_pass": 0.0,
                "secret_pii_leak_count": 1,
                "raw_persistence_count": 1,
                "tool_policy_violation_count": 1,
            },
            thresholds={
                "block_recall": 1.0,
                "malicious_document_pass": 1.0,
                "malicious_retrieved_evidence_pass": 1.0,
                "malicious_tool_output_pass": 1.0,
                "artifact_redaction_scan_pass": 1.0,
                "publishable_allowlist_pass": 1.0,
                "retention_scope_pass": 1.0,
                "secret_pii_leak_count": 0,
                "raw_persistence_count": 0,
                "tool_policy_violation_count": 0,
            },
            extra={
                "publishable_allowlist_path": "artifacts/security_redteam/publishable_allowlist.md",
                "retention_scope_path": "artifacts/security_redteam/retention_scope.md",
            },
        ),
        "artifacts/cost_budget/summary.json": _not_measured_payload(
            complete_field="cost_budget_complete",
            metrics={
                "token_record_coverage": 0.0,
                "cost_record_coverage": 0.0,
                "budget_violation_count": 1,
            },
            thresholds={
                "token_record_coverage": 1.0,
                "cost_record_coverage": 1.0,
                "budget_violation_count": 0,
            },
            extra={
                "real_open_run_cost_estimate_usd": 0.0,
                "regression_threshold_rationale": "not measured; real lane requires explicit approval",
            },
        ),
    }


def write_stage2_scaffold(
    *,
    root: Path = Path("."),
    eval_dir: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    eval_dir = eval_dir.resolve() if eval_dir else root / "artifacts/eval"
    coverage = _coverage_payload(root, eval_dir)
    _write_json(root / "artifacts/eval_stage2/coverage.json", coverage)
    _write_eval_stage2_support(root, coverage)

    written = ["artifacts/eval_stage2/coverage.json"]
    for rel, payload in _placeholder_payloads(root, coverage["eval_set_hash"]).items():
        existing = _read_json(root / rel)
        if _is_completed_payload(existing) or _is_measured_failure_payload(existing):
            payload = existing
        else:
            _write_json(root / rel, payload)
        written.append(rel)

    summary = {
        "stage2_scaffold_complete": True,
        "root": str(root),
        "source_eval_dir": _display_path(eval_dir, root),
        "eval_set_hash": coverage["eval_set_hash"],
        "artifact_count": len(written),
        "artifacts": written,
        "final_readiness_claim": False,
        "note": "Scaffold artifacts are fail-closed until each gate is measured by its lane.",
    }
    _write_json(root / "artifacts/stage2_scaffold/summary.json", summary)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write fail-closed Stage 2 portfolio artifact scaffolds."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--eval-dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    summary = write_stage2_scaffold(root=args.root, eval_dir=args.eval_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
