from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .index_store import SearchResult


@dataclass(frozen=True)
class VisualEvidenceIndex:
    by_doc_id: dict[str, list[dict[str, Any]]]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _parse_record_id(record_id: str) -> tuple[str, int, str]:
    parts = record_id.split(":")
    if len(parts) < 4 or parts[0] != "doc" or not parts[2].startswith("p"):
        raise ValueError(f"malformed visual record_id: {record_id}")
    doc_id = ":".join(parts[:2])
    try:
        page = int(parts[2][1:])
    except ValueError as exc:
        raise ValueError(f"malformed visual record_id: {record_id}") from exc
    visual_type = ":".join(parts[3:])
    if not visual_type:
        raise ValueError(f"malformed visual record_id: {record_id}")
    return doc_id, page, visual_type


def load_visual_sidecar(
    candidate_path: Path | str,
    gate_summary_path: Path | str | None = None,
) -> VisualEvidenceIndex:
    if gate_summary_path is None:
        raise ValueError("visual candidate gate summary is required")
    gate = _read_json(Path(gate_summary_path))
    if gate.get("ok") is not True:
        raise ValueError("visual candidate gate did not pass")

    by_doc_id: dict[str, list[dict[str, Any]]] = {}
    for row in _read_jsonl(Path(candidate_path)):
        doc_id, page, visual_type = _parse_record_id(str(row["record_id"]))
        evidence = {
            "record_id": row["record_id"],
            "doc_id": doc_id,
            "page": page,
            "visual_type": visual_type,
            "fact_type": row.get("fact_type"),
            "field": row.get("field"),
            "value": row.get("value"),
            "extractor": row.get("extractor"),
            "confidence": row.get("confidence"),
        }
        if "matched_keywords" in row:
            evidence["matched_keywords"] = row["matched_keywords"]
        by_doc_id.setdefault(doc_id, []).append(evidence)

    for evidence_rows in by_doc_id.values():
        evidence_rows.sort(key=lambda item: (item["page"], item["record_id"]))
    return VisualEvidenceIndex(by_doc_id=by_doc_id)


def attach_visual_evidence(
    results: Iterable[SearchResult],
    index: VisualEvidenceIndex | None,
    max_per_result: int = 5,
) -> list[SearchResult]:
    if index is None:
        return list(results)

    attached: list[SearchResult] = []
    for result in results:
        evidence = index.by_doc_id.get(result.doc_id, [])[:max_per_result]
        metadata = dict(result.metadata)
        if evidence:
            metadata["visual_evidence"] = [dict(item) for item in evidence]
            metadata["visual_evidence_count"] = len(evidence)
        attached.append(
            SearchResult(
                chunk_id=result.chunk_id,
                doc_id=result.doc_id,
                csv_row_id=result.csv_row_id,
                score=result.score,
                text=result.text,
                metadata=metadata,
            )
        )
    return attached
