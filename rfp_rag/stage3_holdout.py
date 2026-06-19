from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


STAGE3_CONTRACT_VERSION = "rfp-rag-stage3-holdout-v1"

THRESHOLDS = {
    "document_count": 20,
    "query_count": 100,
    "recall@5": 0.90,
    "mrr": 0.80,
    "citation_validity": 0.95,
    "faithfulness": 0.85,
    "answer_relevancy": 0.78,
    "unsupported_visual_claim_rate": 0.05,
    "abstention_precision": 0.90,
}

CASE_REQUIRED_FIELDS = {
    "id",
    "query",
    "query_type",
    "expected_doc_ids",
    "label_source",
    "provenance",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _hash_rows(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256(
        "\n".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows
        ).encode("utf-8")
    ).hexdigest()


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _case_schema_issues(row: dict[str, Any]) -> list[str]:
    issues = [field for field in CASE_REQUIRED_FIELDS if field not in row]
    if not isinstance(row.get("expected_doc_ids"), list) or not row.get(
        "expected_doc_ids"
    ):
        issues.append("expected_doc_ids")
    provenance = row.get("provenance")
    if not isinstance(provenance, dict):
        issues.append("provenance")
    else:
        if provenance.get("corpus_split") != "stage3_independent_holdout":
            issues.append("provenance.corpus_split")
        if provenance.get("stage2_overlap") is not False:
            issues.append("provenance.stage2_overlap")
    if row.get("label_source") not in {
        "manual_blind_label",
        "dual_review_adjudicated",
    }:
        issues.append("label_source")
    return sorted(set(issues))


def audit_stage3_cases(
    *, root: Path = Path("."), cases_path: Path | None = None
) -> dict[str, Any]:
    root = root.resolve()
    cases_path = cases_path or root / "eval_sets/stage3_holdout/cases.jsonl"
    rows = _read_jsonl(cases_path)
    case_issues: list[dict[str, Any]] = []
    doc_ids: set[str] = set()
    counts_by_slice: dict[str, int] = {}
    for row in rows:
        issues = _case_schema_issues(row)
        if issues:
            case_issues.append({"id": row.get("id"), "issues": issues})
        for doc_id in row.get("expected_doc_ids") or []:
            doc_ids.add(str(doc_id))
        query_type = str(row.get("query_type") or "unknown")
        counts_by_slice[query_type] = counts_by_slice.get(query_type, 0) + 1

    metrics = {
        "document_count": len(doc_ids),
        "query_count": len(rows),
    }
    failed: list[str] = []
    if not rows:
        failed.append("cases_missing")
    if case_issues:
        failed.append("case_schema")
    if metrics["document_count"] < THRESHOLDS["document_count"]:
        failed.append("document_count")
    if metrics["query_count"] < THRESHOLDS["query_count"]:
        failed.append("query_count")

    return {
        "stage3_case_audit_complete": not failed,
        "cases_path": _display_path(cases_path, root),
        "eval_set_hash": _hash_rows(rows) if rows else "",
        "counts_by_slice": counts_by_slice,
        "metrics": metrics,
        "thresholds": {
            "document_count": THRESHOLDS["document_count"],
            "query_count": THRESHOLDS["query_count"],
        },
        "case_issues": case_issues,
        "failed": failed,
    }


def _write_support_docs(root: Path, audit: dict[str, Any]) -> tuple[Path, Path]:
    split_manifest_path = root / "artifacts/eval_stage3_holdout/split_manifest.json"
    label_rubric_path = root / "artifacts/eval_stage3_holdout/label_rubric.md"
    _write_json(
        split_manifest_path,
        {
            "contract_version": STAGE3_CONTRACT_VERSION,
            "policy": "independent_stage3_holdout",
            "cases_path": audit["cases_path"],
            "eval_set_hash": audit["eval_set_hash"],
            "required_document_count": THRESHOLDS["document_count"],
            "required_query_count": THRESHOLDS["query_count"],
            "stage2_overlap_allowed": False,
            "tuning_after_freeze_allowed": False,
        },
    )
    _write_text(
        label_rubric_path,
        "# Stage 3 Label Rubric\n\n"
        "- Cases must come from the Stage 3 independent holdout split.\n"
        "- `label_source` must be `manual_blind_label` or `dual_review_adjudicated`.\n"
        "- Each case must include expected document ids and provenance fields.\n"
        "- Stage 2 overlap is not allowed.\n"
        "- Real-provider quality metrics must be finalized only after explicit paid/API approval.\n",
    )
    return split_manifest_path, label_rubric_path


def finalize_stage3_holdout(
    *,
    root: Path = Path("."),
    cases_path: Path | None = None,
    raw_metrics_path: Path | None = None,
    out: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    out = out or root / "artifacts/eval_stage3_holdout/metrics.json"
    raw_metrics_path = (
        raw_metrics_path or root / "artifacts/eval_stage3_raw/metrics.json"
    )
    audit = audit_stage3_cases(root=root, cases_path=cases_path)
    split_manifest_path, label_rubric_path = _write_support_docs(root, audit)
    raw = _read_json(raw_metrics_path)
    raw_metrics = raw.get("aggregate") or raw.get("metrics") or {}

    metrics = {
        "document_count": audit["metrics"]["document_count"],
        "query_count": audit["metrics"]["query_count"],
        "recall@5": raw_metrics.get("recall@5", 0.0),
        "mrr": raw_metrics.get("mrr", 0.0),
        "citation_validity": raw_metrics.get("citation_validity", 0.0),
        "faithfulness": raw_metrics.get("faithfulness", 0.0),
        "answer_relevancy": raw_metrics.get("answer_relevancy", 0.0),
        "unsupported_visual_claim_rate": raw_metrics.get(
            "unsupported_visual_claim_rate", 1.0
        ),
        "abstention_precision": raw_metrics.get("abstention_precision", 0.0),
    }
    failed = list(audit["failed"])
    if not raw:
        failed.append("stage3_real_metrics_missing")
    for key, threshold in THRESHOLDS.items():
        value = metrics[key]
        if key == "unsupported_visual_claim_rate":
            if value > threshold:
                failed.append(key)
        elif value < threshold:
            failed.append(key)

    summary = {
        "stage3_holdout_quality_complete": not failed,
        "contract_version": STAGE3_CONTRACT_VERSION,
        "corpus_split_manifest_path": _display_path(split_manifest_path, root),
        "label_rubric_path": _display_path(label_rubric_path, root),
        "eval_set_hash": audit["eval_set_hash"],
        "query_set_counts": {
            "total": audit["metrics"]["query_count"],
            **audit["counts_by_slice"],
        },
        "required_command": (
            "uv run python -m rfp_rag.stage3_holdout "
            "--raw-metrics artifacts/eval_stage3_raw/metrics.json"
        ),
        "raw_metrics_path": _display_path(raw_metrics_path, root),
        "metrics": metrics,
        "thresholds": dict(THRESHOLDS),
        "failed": sorted(set(failed)),
    }
    _write_json(out, summary)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Finalize Stage 3 independent holdout readiness/quality contract."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--raw-metrics", type=Path)
    parser.add_argument("--out", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    summary = finalize_stage3_holdout(
        root=args.root,
        cases_path=args.cases,
        raw_metrics_path=args.raw_metrics,
        out=args.out,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["stage3_holdout_quality_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
