from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Callable

import pytest


@pytest.fixture
def parsed_manifest_factory(tmp_path: Path) -> Callable[[Path], Path]:
    """Create lightweight parsed-source artifacts for tests.

    The fixture writes fake parser outputs so build/index tests do not depend on
    local HWP/PDF parser binaries. Production code still treats CSV as metadata
    and reads document body text from the parse manifest.
    """

    def make(csv_path: Path) -> Path:
        out_dir = tmp_path / "parsed_fixture"
        text_dir = out_dir / "text"
        text_dir.mkdir(parents=True, exist_ok=True)
        rows: list[dict[str, object]] = []
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                doc_id = f"doc:{idx:03d}"
                text_path = text_dir / f"doc_{idx:03d}.txt"
                source_text = "\n".join(
                    [
                        "Ⅰ",
                        "사업 안내",
                        "1",
                        "사업개요",
                        row.get("텍스트", ""),
                        "Ⅳ",
                        "제안안내 사항",
                        "2",
                        "제안서 평가방법",
                        "평가 기준은 기술능력평가와 가격평가로 구성한다.",
                    ]
                )
                text_path.write_text(source_text, encoding="utf-8")
                suffix = Path(row.get("파일명", "")).suffix.lower()
                rows.append(
                    {
                        "doc_id": doc_id,
                        "parse_status": "parsed",
                        "parser_backend": "pymupdf" if suffix == ".pdf" else "unhwp",
                        "text_path": str(text_path),
                        "content_source": "source_pdf_text"
                        if suffix == ".pdf"
                        else "source_hwp_text",
                        "source_quality": "source_parsed",
                        "citation_level": "document",
                        "page_citation_available": False,
                        "page_text_path": None,
                        "converted_pdf_path": None,
                        "error_reason": None,
                    }
                )
        manifest_path = out_dir / "manifest.jsonl"
        with manifest_path.open("w", encoding="utf-8") as f:
            for record in rows:
                f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return manifest_path

    return make
