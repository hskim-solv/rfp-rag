from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from .contracts import AGENT_CONTRACT_VERSION, CONTRACT_VERSION, REAL_CONTRACT_VERSION


GATE_SPECS = {
    "offline_rag": {
        "path": "artifacts/eval/metrics.json",
        "gate_key": "offline_scaffold_complete",
        "contract_path": "artifacts/eval/contract.json",
        "expected_contract_version": CONTRACT_VERSION,
        "expected_provider_lane": "offline",
        "expected_thresholds_met": False,
        "expected_evaluation_valid": True,
        "expected_query_set_counts": {
            "abstention": 30,
            "curated_text": 10,
            "golden_metadata": 400,
            "section_lookup": 30,
            "total": 470,
        },
        "expected_retrieval_mode": "vector",
        "expected_reranker": "none",
        "expected_min_score": 0.34,
        "expected_top_k": 5,
        "index_manifest_path": "artifacts/index/manifest.json",
        "expected_index_embedding_provider": "offline",
        "requires_predictions": True,
        "required_command_fragments": (
            "--index artifacts/index",
            "--provider offline",
            "--min-score 0.34",
        ),
    },
    "real_rag": {
        "path": "artifacts/eval_real/metrics.json",
        "gate_key": "rag_quality_complete",
        "contract_path": "artifacts/eval_real/contract.json",
        "expected_contract_version": REAL_CONTRACT_VERSION,
        "expected_provider_lane": "real_openai",
        "expected_thresholds_met": True,
        "expected_evaluation_valid": True,
        "expected_query_set_counts": {
            "abstention": 30,
            "curated_text": 10,
            "golden_metadata": 400,
            "section_lookup": 30,
            "total": 470,
        },
        "expected_retrieval_mode": "vector",
        "expected_reranker": "none",
        "expected_min_score": 0.47,
        "expected_top_k": 5,
        "index_manifest_path": "artifacts/index_real/manifest.json",
        "expected_index_embedding_provider": "real_openai",
        "requires_predictions": True,
        "required_command_fragments": (
            "--out artifacts/index_real",
            "--embedding-provider openai",
            "--parse-manifest artifacts/parsed_docs/manifest.jsonl",
            "--index artifacts/index_real",
            "--provider real_openai",
            "--min-score 0.47",
        ),
    },
    "agent_offline": {
        "path": "artifacts/eval_agent/metrics.json",
        "gate_key": "agent_lane_complete",
        "contract_path": "artifacts/eval_agent/contract.json",
        "expected_contract_version": AGENT_CONTRACT_VERSION,
        "expected_min_score": 0.34,
        "expected_top_k": 5,
        "expected_lane": "offline",
        "expected_agent_counts": {
            "abstention": 30,
            "regression": 20,
            "rewrite": 5,
            "routing": 20,
            "tool": 10,
        },
        "index_manifest_path": "artifacts/index/manifest.json",
        "expected_index_embedding_provider": "offline",
        "requires_predictions": True,
        "required_command_fragments": (
            "--index artifacts/index",
            "--provider offline",
            "--min-score 0.34",
        ),
    },
    "visual_candidate": {
        "path": "artifacts/visual_tesseract_candidate_expanded_gate/summary.json",
        "gate_key": "ok",
        "expected_decision": "visual_candidate_gate",
    },
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _issue(
    code: str,
    message: str,
    *,
    expected: Any = None,
    actual: Any = None,
    path: str | None = None,
) -> dict[str, Any]:
    issue: dict[str, Any] = {"code": code, "message": message}
    if expected is not None:
        issue["expected"] = expected
    if actual is not None:
        issue["actual"] = actual
    if path is not None:
        issue["path"] = path
    return issue


def _append_expected_value_issue(
    issues: list[dict[str, Any]],
    *,
    payload: dict[str, Any],
    key: str,
    expected: Any,
    code: str,
    path: str,
) -> None:
    actual = payload.get(key)
    if actual != expected:
        issues.append(
            _issue(
                code,
                f"{key} does not match expected gate policy",
                expected=expected,
                actual=actual,
                path=path,
            )
        )


def _count_jsonl(path: Path) -> tuple[int, str | None]:
    count = 0
    try:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                json.loads(line)
                count += 1
    except json.JSONDecodeError as exc:
        return count, f"line {line_number}: {exc}"
    return count, None


def _validate_parse_manifest(
    root: Path,
    parse_manifest_path_value: str,
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    parse_manifest_path = root / parse_manifest_path_value
    if not parse_manifest_path.exists():
        issues.append(
            _issue(
                "parse_manifest_missing",
                "parse manifest referenced by index does not exist",
                path=parse_manifest_path_value,
            )
        )
        return {"parse_manifest_present": False}

    doc_ids: set[str] = set()
    count = 0
    non_parsed_count = 0
    try:
        with parse_manifest_path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                record = json.loads(line)
                count += 1
                doc_id = record.get("doc_id")
                if isinstance(doc_id, str):
                    doc_ids.add(doc_id)
                if record.get("parse_status") != "parsed":
                    non_parsed_count += 1
    except json.JSONDecodeError as exc:
        issues.append(
            _issue(
                "parse_manifest_invalid_json",
                f"line {line_number}: {exc}",
                path=parse_manifest_path_value,
            )
        )
        return {"parse_manifest_present": True}

    if count != 100:
        issues.append(
            _issue(
                "parse_manifest_count_mismatch",
                "parse manifest must contain one row for each source document",
                expected=100,
                actual=count,
                path=parse_manifest_path_value,
            )
        )
    if len(doc_ids) != 100:
        issues.append(
            _issue(
                "parse_manifest_doc_count_mismatch",
                "parse manifest must contain 100 unique doc_id values",
                expected=100,
                actual=len(doc_ids),
                path=parse_manifest_path_value,
            )
        )
    if non_parsed_count:
        issues.append(
            _issue(
                "parse_manifest_unparsed_rows_present",
                "parse manifest contains non-parsed rows",
                expected=0,
                actual=non_parsed_count,
                path=parse_manifest_path_value,
            )
        )

    return {
        "parse_manifest_present": True,
        "parse_manifest_row_count": count,
        "parse_manifest_doc_count": len(doc_ids),
    }


def _validate_chunks(
    root: Path,
    manifest_path_value: str,
    manifest: dict[str, Any],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    chunks_path_value = str(Path(manifest_path_value).with_name("chunks.jsonl"))
    chunks_path = root / chunks_path_value
    if not chunks_path.exists():
        issues.append(
            _issue(
                "chunks_missing",
                "index chunks artifact is missing",
                path=chunks_path_value,
            )
        )
        return {"chunks_present": False}

    chunk_count, error = _count_jsonl(chunks_path)
    if error:
        issues.append(_issue("chunks_invalid_json", error, path=chunks_path_value))
        return {"chunks_present": True}

    expected_chunk_count = manifest.get("chunk_count")
    if chunk_count != expected_chunk_count:
        issues.append(
            _issue(
                "chunks_line_count_mismatch",
                "chunks.jsonl line count must match index manifest chunk_count",
                expected=expected_chunk_count,
                actual=chunk_count,
                path=chunks_path_value,
            )
        )

    return {"chunks_present": True, "chunks_line_count": chunk_count}


def _contract_status(
    root: Path,
    spec: dict[str, Any],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    contract_path_value = spec.get("contract_path")
    if not contract_path_value:
        return {}

    contract_path = root / contract_path_value
    if not contract_path.exists():
        issues.append(
            _issue(
                "contract_missing",
                "contract artifact is missing",
                path=contract_path_value,
            )
        )
        return {"contract_present": False}

    try:
        contract = _read_json(contract_path)
    except json.JSONDecodeError as exc:
        issues.append(
            _issue(
                "contract_invalid_json",
                str(exc),
                path=contract_path_value,
            )
        )
        return {"contract_present": True}

    expected_version = spec.get("expected_contract_version")
    actual_version = contract.get("contract_version")
    if expected_version is not None and actual_version != expected_version:
        issues.append(
            _issue(
                "contract_version_mismatch",
                "contract_version does not match current lane contract",
                expected=expected_version,
                actual=actual_version,
                path=contract_path_value,
            )
        )

    required_commands = contract.get("required_commands", [])
    command_text = "\n".join(str(command) for command in required_commands)
    missing_fragments = [
        fragment
        for fragment in spec.get("required_command_fragments", ())
        if fragment not in command_text
    ]
    if missing_fragments:
        issues.append(
            _issue(
                "required_command_mismatch",
                "contract required_commands are missing current gate fragments",
                expected=list(spec.get("required_command_fragments", ())),
                actual=required_commands,
                path=contract_path_value,
            )
        )

    return {
        "contract_path": contract_path_value,
        "contract_present": True,
        "contract_version": actual_version,
    }


def _index_status(
    root: Path,
    spec: dict[str, Any],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    manifest_path_value = spec.get("index_manifest_path")
    if not manifest_path_value:
        return {}

    manifest_path = root / manifest_path_value
    if not manifest_path.exists():
        issues.append(
            _issue(
                "index_manifest_missing",
                "index manifest is missing",
                path=manifest_path_value,
            )
        )
        return {"index_manifest_present": False}

    try:
        manifest = _read_json(manifest_path)
    except json.JSONDecodeError as exc:
        issues.append(
            _issue("index_manifest_invalid_json", str(exc), path=manifest_path_value)
        )
        return {"index_manifest_present": True}

    expected_embedding_provider = spec.get("expected_index_embedding_provider")
    if (
        expected_embedding_provider is not None
        and manifest.get("embedding_provider") != expected_embedding_provider
    ):
        issues.append(
            _issue(
                "index_embedding_provider_mismatch",
                "index embedding provider does not match lane policy",
                expected=expected_embedding_provider,
                actual=manifest.get("embedding_provider"),
                path=manifest_path_value,
            )
        )

    expected_parse_manifest = "artifacts/parsed_docs/manifest.jsonl"
    if manifest.get("text_source") != "parsed":
        issues.append(
            _issue(
                "index_text_source_mismatch",
                "index must be built from parsed source artifacts",
                expected="parsed",
                actual=manifest.get("text_source"),
                path=manifest_path_value,
            )
        )
    if manifest.get("parse_manifest_path") != expected_parse_manifest:
        issues.append(
            _issue(
                "index_parse_manifest_mismatch",
                "index parse manifest lineage does not match source-first policy",
                expected=expected_parse_manifest,
                actual=manifest.get("parse_manifest_path"),
                path=manifest_path_value,
            )
        )
    source_counts = manifest.get("index_text_source_counts")
    parsed_count = (
        source_counts.get("parsed") if isinstance(source_counts, dict) else None
    )
    if parsed_count != 100:
        issues.append(
            _issue(
                "index_text_source_counts_mismatch",
                "index must contain parsed-source chunks for all 100 documents",
                expected={"parsed": 100},
                actual=manifest.get("index_text_source_counts"),
                path=manifest_path_value,
            )
        )
    if manifest.get("unique_docs") != 100:
        issues.append(
            _issue(
                "index_unique_docs_mismatch",
                "index unique document count does not match corpus size",
                expected=100,
                actual=manifest.get("unique_docs"),
                path=manifest_path_value,
            )
        )

    status: dict[str, Any] = {}
    parse_manifest_path_value = manifest.get("parse_manifest_path")
    if isinstance(parse_manifest_path_value, str):
        status.update(_validate_parse_manifest(root, parse_manifest_path_value, issues))
    status.update(_validate_chunks(root, manifest_path_value, manifest, issues))

    return {
        **status,
        "index_manifest_path": manifest_path_value,
        "index_manifest_present": True,
        "index_created_at": manifest.get("created_at"),
        "index_text_source": manifest.get("text_source"),
        "index_parse_manifest_path": manifest.get("parse_manifest_path"),
        "index_embedding_provider": manifest.get("embedding_provider"),
        "index_chunk_count": manifest.get("chunk_count"),
    }


def _expected_prediction_count(payload: dict[str, Any]) -> int | None:
    query_set_counts = payload.get("query_set_counts")
    if isinstance(query_set_counts, dict) and isinstance(
        query_set_counts.get("total"), int
    ):
        return query_set_counts["total"]

    counts = payload.get("counts")
    if isinstance(counts, dict) and all(
        isinstance(value, int) for value in counts.values()
    ):
        return sum(counts.values())
    return None


def _validate_predictions(
    root: Path,
    metrics_path_value: str,
    payload: dict[str, Any],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    predictions_path_value = str(
        Path(metrics_path_value).with_name("predictions.jsonl")
    )
    predictions_path = root / predictions_path_value
    if not predictions_path.exists():
        issues.append(
            _issue(
                "predictions_missing",
                "predictions artifact is missing",
                path=predictions_path_value,
            )
        )
        return {"predictions_present": False}

    prediction_count, error = _count_jsonl(predictions_path)
    if error:
        issues.append(
            _issue("predictions_invalid_json", error, path=predictions_path_value)
        )
        return {"predictions_present": True}

    expected_count = _expected_prediction_count(payload)
    if expected_count is None:
        issues.append(
            _issue(
                "predictions_expected_count_unavailable",
                "metrics artifact does not expose a usable prediction count",
                path=metrics_path_value,
            )
        )
    elif prediction_count != expected_count:
        issues.append(
            _issue(
                "predictions_line_count_mismatch",
                "predictions.jsonl line count must match metrics counts",
                expected=expected_count,
                actual=prediction_count,
                path=predictions_path_value,
            )
        )

    return {"predictions_present": True, "predictions_line_count": prediction_count}


def _validate_visual_candidate(
    payload: dict[str, Any],
    spec: dict[str, Any],
    path: str,
    issues: list[dict[str, Any]],
) -> None:
    expected_decision = spec.get("expected_decision")
    if expected_decision is not None and payload.get("decision") != expected_decision:
        issues.append(
            _issue(
                "visual_decision_mismatch",
                "visual gate decision does not match expected value",
                expected=expected_decision,
                actual=payload.get("decision"),
                path=path,
            )
        )
    if payload.get("failures"):
        issues.append(
            _issue(
                "visual_gate_failures_present",
                "visual gate has recorded failures",
                actual=payload.get("failures"),
                path=path,
            )
        )

    metrics = payload.get("metrics", {})
    thresholds = payload.get("thresholds", {})
    comparisons = (
        ("precision", ">=", "min_precision"),
        ("recall", ">=", "min_recall"),
        ("f1", ">=", "min_f1"),
        ("negative_violation_count", "<=", "max_negative_violation_count"),
    )
    for metric_key, operator, threshold_key in comparisons:
        if metric_key not in metrics or threshold_key not in thresholds:
            issues.append(
                _issue(
                    "visual_threshold_missing",
                    "visual gate metric or threshold is missing",
                    expected=threshold_key,
                    actual=metric_key,
                    path=path,
                )
            )
            continue
        metric_value = metrics[metric_key]
        threshold_value = thresholds[threshold_key]
        passes = (
            metric_value >= threshold_value
            if operator == ">="
            else metric_value <= threshold_value
        )
        if not passes:
            issues.append(
                _issue(
                    "visual_threshold_mismatch",
                    "visual gate metric does not satisfy threshold",
                    expected=f"{metric_key} {operator} {threshold_value}",
                    actual=metric_value,
                    path=path,
                )
            )


def _lane_status(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    relative_path = spec["path"]
    gate_key = spec["gate_key"]
    path = root / relative_path
    base: dict[str, Any] = {
        "gate_key": gate_key,
        "path": relative_path,
        "present": path.exists(),
        "issues": [],
    }
    if not path.exists():
        return {**base, "ok": False, "value": None}
    try:
        payload = _read_json(path)
    except json.JSONDecodeError as exc:
        return {
            **base,
            "ok": False,
            "value": None,
            "issues": [
                _issue("metrics_invalid_json", str(exc), path=relative_path),
            ],
        }

    issues: list[dict[str, Any]] = []
    value = payload.get(gate_key)
    if value is not True:
        issues.append(
            _issue(
                "gate_value_not_true",
                "gate key is not true",
                expected=True,
                actual=value,
                path=relative_path,
            )
        )
    status = {**base, "value": value}
    for optional_key in (
        "provider_lane",
        "decision",
        "thresholds_met",
        "evaluation_valid",
        "retrieval_mode",
        "reranker",
        "reaggregated_from_predictions",
        "min_score",
        "top_k",
    ):
        if optional_key in payload:
            status[optional_key] = payload[optional_key]
    failed = payload.get("gate", {}).get("failed")
    if failed is not None:
        status["failed"] = failed
    if failed:
        issues.append(
            _issue(
                "gate_failed_entries_present",
                "gate failed entries are present",
                actual=failed,
                path=relative_path,
            )
        )

    status.update(_contract_status(root, spec, issues))
    status.update(_index_status(root, spec, issues))
    if spec.get("requires_predictions"):
        status.update(_validate_predictions(root, relative_path, payload, issues))

    expected_values = (
        ("provider_lane", "expected_provider_lane", "provider_lane_mismatch"),
        ("thresholds_met", "expected_thresholds_met", "thresholds_met_mismatch"),
        (
            "evaluation_valid",
            "expected_evaluation_valid",
            "evaluation_valid_mismatch",
        ),
        ("query_set_counts", "expected_query_set_counts", "query_set_counts_mismatch"),
        ("retrieval_mode", "expected_retrieval_mode", "retrieval_mode_mismatch"),
        ("reranker", "expected_reranker", "reranker_mismatch"),
        ("min_score", "expected_min_score", "min_score_mismatch"),
        ("top_k", "expected_top_k", "top_k_mismatch"),
        ("lane", "expected_lane", "lane_mismatch"),
        ("counts", "expected_agent_counts", "counts_mismatch"),
    )
    for payload_key, spec_key, code in expected_values:
        if spec_key in spec:
            _append_expected_value_issue(
                issues,
                payload=payload,
                key=payload_key,
                expected=spec[spec_key],
                code=code,
                path=relative_path,
            )

    if payload.get("reaggregated_from_predictions") is True:
        issues.append(
            _issue(
                "reaggregated_from_predictions_unexpected",
                "gate status requires a fresh lane artifact, not reaggregated predictions",
                expected=False,
                actual=True,
                path=relative_path,
            )
        )

    if relative_path.endswith("summary.json"):
        _validate_visual_candidate(payload, spec, relative_path, issues)

    status["issues"] = issues
    status["ok"] = value is True and not issues
    return status


def collect_gate_status(root: Path | str = ".") -> dict[str, Any]:
    root_path = Path(root)
    lanes = {name: _lane_status(root_path, spec) for name, spec in GATE_SPECS.items()}
    return {
        "overall_ok": all(lane["ok"] for lane in lanes.values()),
        "root": str(root_path),
        "lanes": lanes,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Print read-only RFP RAG gate status as JSON."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    status = collect_gate_status(args.root)
    print(
        json.dumps(
            status,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status["overall_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
