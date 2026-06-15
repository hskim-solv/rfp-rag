from __future__ import annotations

import argparse
import csv
import hashlib
import json
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Literal

REQUIRED_COLUMNS = ["사업명", "발주 기관", "사업 요약", "파일명", "텍스트"]
ALL_COLUMNS = [
    "공고 번호",
    "공고 차수",
    "사업명",
    "사업 금액",
    "발주 기관",
    "공개 일자",
    "입찰 참여 시작일",
    "입찰 참여 마감일",
    "사업 요약",
    "파일형식",
    "파일명",
    "텍스트",
]


@dataclass(frozen=True)
class CorpusDocument:
    csv_row_id: str
    doc_id: str
    text: str
    metadata: dict[str, Any]


def normalize_filename(
    value: str, form: Literal["NFC", "NFD", "NFKC", "NFKD"] = "NFC"
) -> str:
    return unicodedata.normalize(form, value or "")


def _safe_int_from_float_string(value: str) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return int(float(text.replace(",", "")))
    except ValueError:
        return None


def _iso_datetime(value: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    # Dataset uses ``YYYY-MM-DD HH:MM:SS``. Keep a small fallback for ISO-ish inputs.
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).isoformat()
        except ValueError:
            continue
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_filename_map(files_dir: Path) -> dict[str, Path]:
    """Return a basename map that resolves exact, NFC, and NFD spellings."""
    mapping: dict[str, Path] = {}
    if not files_dir.exists():
        return mapping
    for path in files_dir.iterdir():
        if not path.is_file():
            continue
        for key in {
            path.name,
            normalize_filename(path.name, "NFC"),
            normalize_filename(path.name, "NFD"),
        }:
            mapping.setdefault(key, path)
    return mapping


def _read_rows(csv_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [{k: (v or "") for k, v in row.items()} for row in reader]
        return list(reader.fieldnames or []), rows


def _metadata_for(
    row: dict[str, str], row_index: int, resolved_path: Path | None
) -> dict[str, Any]:
    csv_filename = row.get("파일명", "")
    round_int = _safe_int_from_float_string(row.get("공고 차수", ""))
    metadata: dict[str, Any] = {
        "csv_row_index": row_index,
        "csv_row_id": f"{row_index:03d}",
        "notice_number": row.get("공고 번호", ""),
        "notice_round_raw": row.get("공고 차수", ""),
        "notice_round_int": round_int,
        "notice_round_string": "" if round_int is None else str(round_int),
        "project_name": row.get("사업명", ""),
        "budget_raw": row.get("사업 금액", ""),
        "budget_krw_int": _safe_int_from_float_string(row.get("사업 금액", "")),
        "issuer": row.get("발주 기관", ""),
        "published_at_raw": row.get("공개 일자", ""),
        "published_at_iso": _iso_datetime(row.get("공개 일자", "")),
        "bid_start_at_raw": row.get("입찰 참여 시작일", ""),
        "bid_start_at_iso": _iso_datetime(row.get("입찰 참여 시작일", "")),
        "bid_end_at_raw": row.get("입찰 참여 마감일", ""),
        "bid_end_at_iso": _iso_datetime(row.get("입찰 참여 마감일", "")),
        "summary": row.get("사업 요약", ""),
        "file_type": row.get("파일형식", ""),
        "csv_filename_raw": csv_filename,
        "csv_filename_nfc": normalize_filename(csv_filename, "NFC"),
        "csv_filename_nfd": normalize_filename(csv_filename, "NFD"),
        "resolved_filesystem_path": str(resolved_path) if resolved_path else None,
    }
    # Preserve original Korean metadata too for report/debug traceability.
    for key in ALL_COLUMNS:
        metadata[key] = row.get(key, "")
    return metadata


def load_corpus(csv_path: Path | str, files_dir: Path | str) -> list[CorpusDocument]:
    csv_path = Path(csv_path)
    files_dir = Path(files_dir)
    _, rows = _read_rows(csv_path)
    file_map = resolve_filename_map(files_dir)
    docs: list[CorpusDocument] = []
    for idx, row in enumerate(rows):
        csv_filename = row.get("파일명", "")
        resolved = (
            file_map.get(csv_filename)
            or file_map.get(normalize_filename(csv_filename, "NFC"))
            or file_map.get(normalize_filename(csv_filename, "NFD"))
        )
        csv_row_id = f"{idx:03d}"
        docs.append(
            CorpusDocument(
                csv_row_id=csv_row_id,
                doc_id=f"doc:{csv_row_id}",
                text="",
                metadata=_metadata_for(row, idx, resolved),
            )
        )
    return docs


def inspect_corpus(
    csv_path: Path | str, files_dir: Path | str, out: Path | str | None = None
) -> dict[str, Any]:
    csv_path = Path(csv_path)
    files_dir = Path(files_dir)
    columns, rows = _read_rows(csv_path)
    raw_file_names = (
        {p.name for p in files_dir.iterdir() if p.is_file()}
        if files_dir.exists()
        else set()
    )
    docs = load_corpus(csv_path, files_dir)

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in columns]
    text_nonempty_count = sum(1 for row in rows if row.get("텍스트", "").strip())
    raw_file_matches = sum(1 for row in rows if row.get("파일명", "") in raw_file_names)
    normalized_file_matches = sum(
        1 for doc in docs if doc.metadata.get("resolved_filesystem_path")
    )
    suffix_counts = Counter(Path(row.get("파일명", "")).suffix.lower() for row in rows)
    suffix_counts.pop("", None)

    warnings: list[str] = []
    if missing_columns:
        warnings.append(f"missing_required_columns:{','.join(missing_columns)}")
    empty_required = [
        f"row:{idx:03d}:{col}"
        for idx, row in enumerate(rows)
        for col in REQUIRED_COLUMNS
        if not row.get(col, "").strip()
    ]
    if empty_required:
        warnings.append(f"empty_required_values:{len(empty_required)}")
    if normalized_file_matches != len(rows):
        warnings.append(f"unresolved_files:{len(rows) - normalized_file_matches}")

    manifest: dict[str, Any] = {
        "data_path": str(csv_path),
        "files_path": str(files_dir),
        "csv_sha256": sha256_file(csv_path),
        "row_count": len(rows),
        "columns": columns,
        "required_columns": REQUIRED_COLUMNS,
        "required_columns_present": not missing_columns,
        "text_nonempty_count": text_nonempty_count,
        "raw_file_matches": raw_file_matches,
        "normalized_file_matches": normalized_file_matches,
        "suffix_counts": dict(sorted(suffix_counts.items())),
        "row_id_convention": "0-based zero-padded 3 digits",
        "doc_id_pattern": "doc:{csv_row_id}",
        "warnings": warnings,
    }
    if out is not None:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return manifest


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect the RFP CSV metadata registry."
    )
    parser.add_argument(
        "--data", required=True, type=Path, help="Path to data_list.csv"
    )
    parser.add_argument(
        "--files", required=True, type=Path, help="Path to source file directory"
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="Manifest JSON output path"
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    manifest = inspect_corpus(args.data, args.files, args.out)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0
