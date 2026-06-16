from __future__ import annotations

import json
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

EXTRACTOR_NAME = "visual_tesseract_ocr_candidate_v2"
REVIEW_STATUS_FILTER = "reviewed_needs_extraction"


@dataclass(frozen=True)
class VisualOcrRule:
    fact_type: str
    field: str
    keywords: tuple[str, ...]
    min_keyword_count: int = 1
    required_keywords_any: tuple[str, ...] = ()
    solitary_keywords: tuple[str, ...] = ()
    emit_candidate: bool = True


VISUAL_OCR_RULES: dict[str, VisualOcrRule] = {
    "gantt_schedule": VisualOcrRule(
        fact_type="visual_type_present",
        field="schedule",
        min_keyword_count=3,
        keywords=(
            "일정",
            "추진일정",
            "수행일정",
            "기간",
            "개월",
            "착수",
            "완료",
            "월별",
            "공정",
            "WBS",
            "계획",
        ),
    ),
    "system_architecture_diagram": VisualOcrRule(
        fact_type="visual_type_present",
        field="system_architecture",
        required_keywords_any=("서버", "DB", "인터페이스"),
        solitary_keywords=("연계",),
        keywords=(
            "시스템",
            "구성",
            "아키텍처",
            "서버",
            "DB",
            "데이터베이스",
            "연계",
            "인터페이스",
            "네트워크",
            "API",
            "플랫폼",
        ),
    ),
    "organization_chart": VisualOcrRule(
        fact_type="visual_type_present",
        field="requirements",
        required_keywords_any=("조직", "수행체계"),
        keywords=(
            "조직",
            "추진체계",
            "수행체계",
            "PM",
            "사업관리",
            "역할",
            "인력",
            "담당",
            "책임",
            "팀",
        ),
    ),
    "requirements_table": VisualOcrRule(
        fact_type="visual_type_present",
        field="requirements",
        min_keyword_count=4,
        keywords=("요구사항", "기능", "요건", "항목", "세부", "내용", "구분"),
    ),
}


def _normalize_review_statuses(
    review_statuses: Iterable[str] | None,
) -> tuple[str, ...]:
    values = tuple(
        sorted(
            {
                str(status).strip()
                for status in (review_statuses or (REVIEW_STATUS_FILTER,))
                if str(status).strip()
            }
        )
    )
    return values or (REVIEW_STATUS_FILTER,)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"jsonl file not found: {path}")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"jsonl row must be an object on {path}:{line_number}")
            rows.append(row)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _ocr_text_fixture(path: Path) -> dict[str, str]:
    rows = _read_jsonl(path)
    return {
        str(row.get("record_id") or ""): str(row.get("text") or "")
        for row in rows
        if row.get("record_id")
    }


def _match_keywords(text: str, rule: VisualOcrRule) -> list[str]:
    upper_text = text.upper()
    return [keyword for keyword in rule.keywords if keyword.upper() in upper_text]


def _passes_evidence_gate(matched_keywords: list[str], rule: VisualOcrRule) -> bool:
    if not rule.emit_candidate:
        return False

    matched_keyword_set = set(matched_keywords)
    if len(matched_keyword_set) == 1 and matched_keywords[0] in rule.solitary_keywords:
        return True

    if len(matched_keyword_set) < rule.min_keyword_count:
        return False

    if rule.required_keywords_any and not (
        matched_keyword_set & set(rule.required_keywords_any)
    ):
        return False

    return True


def _candidate_fact(
    record: dict[str, Any],
    rule: VisualOcrRule,
    matched_keywords: list[str],
) -> dict[str, Any]:
    confidence = min(0.95, 0.45 + (0.08 * len(matched_keywords)))
    return {
        "record_id": str(record["record_id"]),
        "fact_type": rule.fact_type,
        "field": rule.field,
        "value": f"{record.get('visual_type')} OCR keyword evidence detected",
        "extractor": EXTRACTOR_NAME,
        "confidence": round(confidence, 4),
        "matched_keywords": matched_keywords,
    }


def build_visual_tesseract_candidates(
    records: Iterable[dict[str, Any]],
    ocr_text_by_record: dict[str, str],
    *,
    review_statuses: Iterable[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    rows = list(records)
    allowed_review_statuses = set(_normalize_review_statuses(review_statuses))
    candidates: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []

    for record in rows:
        record_id = str(record.get("record_id") or "")
        if record.get("review_status") not in allowed_review_statuses:
            observations.append(
                {
                    "record_id": record_id,
                    "status": "skipped_review_status",
                    "ocr_text_length": len(ocr_text_by_record.get(record_id, "")),
                    "matched_keywords": [],
                }
            )
            continue

        text = ocr_text_by_record.get(record_id, "")
        visual_type = str(record.get("visual_type") or "")
        rule = VISUAL_OCR_RULES.get(visual_type)
        if not text.strip():
            observations.append(
                {
                    "record_id": record_id,
                    "status": "empty_ocr_text",
                    "ocr_text_length": 0,
                    "matched_keywords": [],
                }
            )
            continue
        if rule is None:
            observations.append(
                {
                    "record_id": record_id,
                    "status": "unsupported_visual_type",
                    "ocr_text_length": len(text),
                    "matched_keywords": [],
                }
            )
            continue
        matched_keywords = _match_keywords(text, rule)
        if not matched_keywords:
            observations.append(
                {
                    "record_id": record_id,
                    "status": "no_keyword_match",
                    "ocr_text_length": len(text),
                    "matched_keywords": [],
                }
            )
            continue
        if not _passes_evidence_gate(matched_keywords, rule):
            observations.append(
                {
                    "record_id": record_id,
                    "status": "insufficient_ocr_evidence",
                    "ocr_text_length": len(text),
                    "matched_keywords": matched_keywords,
                }
            )
            continue
        candidates.append(_candidate_fact(record, rule, matched_keywords))
        observations.append(
            {
                "record_id": record_id,
                "status": "candidate_emitted",
                "ocr_text_length": len(text),
                "matched_keywords": matched_keywords,
            }
        )

    status_counts = Counter(observation["status"] for observation in observations)
    summary = {
        "decision": "visual_tesseract_ocr_candidate",
        "extractor": EXTRACTOR_NAME,
        "review_status_filter": list(sorted(allowed_review_statuses)),
        "source_record_count": len(rows),
        "ocr_text_record_count": len(ocr_text_by_record),
        "candidate_fact_count": len(candidates),
        "skipped_record_count": status_counts.get("skipped_review_status", 0),
        "empty_ocr_text_count": status_counts.get("empty_ocr_text", 0),
        "no_keyword_match_count": status_counts.get("no_keyword_match", 0),
        "insufficient_ocr_evidence_count": status_counts.get(
            "insufficient_ocr_evidence", 0
        ),
        "unsupported_visual_type_count": status_counts.get(
            "unsupported_visual_type", 0
        ),
        "candidate_emitted_count": status_counts.get("candidate_emitted", 0),
        "status_counts": dict(sorted(status_counts.items())),
    }
    return candidates, summary, observations


def _record_pdf_path(record: dict[str, Any]) -> Path:
    evidence_ref = (
        record.get("evidence_ref")
        if isinstance(record.get("evidence_ref"), dict)
        else {}
    )
    value = record.get("pdf_path") or evidence_ref.get("pdf_path")
    if not value:
        raise ValueError("missing pdf_path")
    return Path(str(value))


def _page_cache_key(record: dict[str, Any]) -> tuple[str, int]:
    return (str(_record_pdf_path(record)), _record_page(record))


def _record_page(record: dict[str, Any]) -> int:
    page = int(record.get("page") or 0)
    if page < 1:
        raise ValueError(f"invalid page: {page}")
    return page


def _render_page_ppm(
    record: dict[str, Any],
    work_dir: Path,
    *,
    dpi: int,
    pdftoppm_bin: str,
    timeout_seconds: int,
) -> Path:
    pdf_path = _record_pdf_path(record)
    page = _record_page(record)
    output_prefix = work_dir / "page"
    subprocess.run(
        [
            pdftoppm_bin,
            "-f",
            str(page),
            "-l",
            str(page),
            "-singlefile",
            "-r",
            str(dpi),
            str(pdf_path),
            str(output_prefix),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
    )
    image_path = output_prefix.with_suffix(".ppm")
    if not image_path.exists():
        raise FileNotFoundError(f"rendered page not found: {image_path}")
    return image_path


def _run_tesseract_stdin(
    image_path: Path,
    *,
    lang: str,
    psm: int,
    tesseract_bin: str,
    timeout_seconds: int,
) -> str:
    image_bytes = image_path.read_bytes()
    result = subprocess.run(
        [tesseract_bin, "stdin", "stdout", "-l", lang, "--psm", str(psm)],
        input=image_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        timeout=timeout_seconds,
    )
    return result.stdout.decode("utf-8", errors="replace")


def _ocr_records(
    records: Iterable[dict[str, Any]],
    *,
    review_statuses: Iterable[str] | None = None,
    dpi: int,
    lang: str,
    psm: int,
    pdftoppm_bin: str,
    tesseract_bin: str,
    timeout_seconds: int,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    ocr_text_by_record: dict[str, str] = {}
    observations: list[dict[str, Any]] = []
    allowed_review_statuses = set(_normalize_review_statuses(review_statuses))
    page_cache: dict[tuple[str, int], tuple[str, dict[str, Any] | None]] = {}
    with tempfile.TemporaryDirectory(prefix="rfp-visual-tesseract-") as tmp:
        root = Path(tmp)
        for record in records:
            record_id = str(record.get("record_id") or "")
            if record.get("review_status") not in allowed_review_statuses:
                continue
            try:
                cache_key = _page_cache_key(record)
            except Exception as exc:  # noqa: BLE001 - lane records per-page failures
                observations.append(
                    {
                        "record_id": record_id,
                        "status": "ocr_error",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                ocr_text_by_record[record_id] = ""
                continue
            if cache_key in page_cache:
                text, cached_error = page_cache[cache_key]
                ocr_text_by_record[record_id] = text
                if cached_error is not None:
                    observations.append(dict(cached_error) | {"record_id": record_id})
                continue
            try:
                work_dir = root / record_id.replace(":", "_")
                work_dir.mkdir(parents=True, exist_ok=True)
                image_path = _render_page_ppm(
                    record,
                    work_dir,
                    dpi=dpi,
                    pdftoppm_bin=pdftoppm_bin,
                    timeout_seconds=timeout_seconds,
                )
                text = _run_tesseract_stdin(
                    image_path,
                    lang=lang,
                    psm=psm,
                    tesseract_bin=tesseract_bin,
                    timeout_seconds=timeout_seconds,
                )
                ocr_text_by_record[record_id] = text
                page_cache[cache_key] = (text, None)
            except Exception as exc:  # noqa: BLE001 - lane records per-page failures
                error_observation = {
                    "status": "ocr_error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                observations.append(dict(error_observation) | {"record_id": record_id})
                page_cache[cache_key] = ("", error_observation)
                ocr_text_by_record[record_id] = ""
    return ocr_text_by_record, observations


def run_visual_tesseract_candidate(
    records_path: Path | str,
    out_dir: Path | str,
    *,
    ocr_text_path: Path | str | None = None,
    dpi: int = 150,
    lang: str = "kor+eng",
    psm: int = 11,
    pdftoppm_bin: str = "pdftoppm",
    tesseract_bin: str = "tesseract",
    timeout_seconds: int = 20,
    review_statuses: Iterable[str] | None = None,
) -> dict[str, Any]:
    records = _read_jsonl(Path(records_path))
    normalized_review_statuses = _normalize_review_statuses(review_statuses)
    if ocr_text_path is None:
        ocr_text_by_record, ocr_error_observations = _ocr_records(
            records,
            review_statuses=normalized_review_statuses,
            dpi=dpi,
            lang=lang,
            psm=psm,
            pdftoppm_bin=pdftoppm_bin,
            tesseract_bin=tesseract_bin,
            timeout_seconds=timeout_seconds,
        )
    else:
        ocr_text_by_record = _ocr_text_fixture(Path(ocr_text_path))
        ocr_error_observations = []

    candidates, summary, observations = build_visual_tesseract_candidates(
        records,
        ocr_text_by_record,
        review_statuses=normalized_review_statuses,
    )
    observations = ocr_error_observations + observations
    if ocr_error_observations:
        summary["ocr_error_count"] = len(ocr_error_observations)
        summary["status_counts"] = dict(
            sorted(
                (
                    Counter(summary["status_counts"])
                    + Counter({"ocr_error": len(ocr_error_observations)})
                ).items()
            )
        )
    else:
        summary["ocr_error_count"] = 0
    summary["dpi"] = dpi
    summary["lang"] = lang
    summary["psm"] = psm
    summary["timeout_seconds"] = timeout_seconds

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out / "candidate_facts.jsonl", candidates)
    _write_jsonl(out / "observations.jsonl", observations)
    _write_json(out / "summary.json", summary)
    return summary
