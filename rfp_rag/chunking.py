from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .corpus import CorpusDocument
from .section_detector import (
    SectionSpan,
    detect_sections,
    extract_requirement_ids,
    find_section_for_span,
)

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+|[^\s]")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    csv_row_id: str
    text: str
    metadata: dict[str, Any]


def token_spans(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0), m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]


def _window_text(
    text: str, spans: list[tuple[str, int, int]], start: int, end: int
) -> str:
    if not spans:
        return text.strip()
    char_start = spans[start][1]
    char_end = spans[end - 1][2]
    return text[char_start:char_end].strip()


def _base_windows(
    text: str,
    spans: list[tuple[str, int, int]],
    chunk_size: int,
    chunk_overlap: int,
) -> list[tuple[int, int, int, int, str, SectionSpan | None]]:
    if not text:
        return [(0, 0, 0, 0, "", None)]
    if len(spans) <= chunk_size:
        return [(0, len(spans), 0, len(text), text, None)]

    windows: list[tuple[int, int, int, int, str, SectionSpan | None]] = []
    step = chunk_size - chunk_overlap
    start = 0
    while start < len(spans):
        end = min(start + chunk_size, len(spans))
        char_start = spans[start][1]
        char_end = spans[end - 1][2]
        windows.append(
            (
                start,
                end,
                char_start,
                char_end,
                _window_text(text, spans, start, end),
                None,
            )
        )
        if end >= len(spans):
            break
        start += step
    return windows


def _range_windows(
    text: str,
    spans: list[tuple[str, int, int]],
    char_start: int,
    char_end: int,
    chunk_size: int,
    chunk_overlap: int,
    section: SectionSpan | None,
) -> list[tuple[int, int, int, int, str, SectionSpan | None]]:
    if char_end <= char_start:
        return []
    range_text = text[char_start:char_end]
    if section is None:
        range_text = re.sub(
            r"^\s*\[PAGE\s+\d+\]\s*$", "", range_text, flags=re.MULTILINE
        )
    if not range_text.strip():
        return []

    token_indexes = [
        idx
        for idx, (_, start, end) in enumerate(spans)
        if start >= char_start and end <= char_end
    ]
    if not token_indexes:
        return []

    windows: list[tuple[int, int, int, int, str, SectionSpan | None]] = []
    step = chunk_size - chunk_overlap
    pos = 0
    while pos < len(token_indexes):
        end_pos = min(pos + chunk_size, len(token_indexes))
        start_token = token_indexes[pos]
        end_token = token_indexes[end_pos - 1] + 1
        window_char_start = spans[start_token][1]
        window_char_end = spans[end_token - 1][2]
        windows.append(
            (
                start_token,
                end_token,
                window_char_start,
                window_char_end,
                _window_text(text, spans, start_token, end_token),
                section,
            )
        )
        if end_pos >= len(token_indexes):
            break
        pos += step
    return windows


def _section_windows(
    text: str,
    spans: list[tuple[str, int, int]],
    sections: list[SectionSpan],
    chunk_size: int,
    chunk_overlap: int,
) -> list[tuple[int, int, int, int, str, SectionSpan | None]]:
    windows: list[tuple[int, int, int, int, str, SectionSpan | None]] = []
    cursor = 0
    for section in sections:
        windows.extend(
            _range_windows(
                text, spans, cursor, section.char_start, chunk_size, chunk_overlap, None
            )
        )
        if text[section.body_start : section.char_end].strip():
            windows.extend(
                _range_windows(
                    text,
                    spans,
                    section.char_start,
                    section.char_end,
                    chunk_size,
                    chunk_overlap,
                    section,
                )
            )
        cursor = max(cursor, section.char_end)
    windows.extend(
        _range_windows(text, spans, cursor, len(text), chunk_size, chunk_overlap, None)
    )

    return windows


def _section_metadata(
    section: SectionSpan | None,
    chunk_text: str,
) -> dict[str, Any]:
    if section is None:
        return {
            "section_title": None,
            "section_type": None,
            "section_path": [],
            "section_index": None,
            "section_level": None,
            "section_page_start": None,
            "section_page_end": None,
            "requirement_ids": extract_requirement_ids(chunk_text),
        }
    return {
        "section_title": section.title,
        "section_type": section.section_type,
        "section_path": list(section.section_path),
        "section_index": section.index,
        "section_level": section.level,
        "section_page_start": section.page_start,
        "section_page_end": section.page_end,
        "requirement_ids": extract_requirement_ids(chunk_text),
    }


def chunk_document(
    doc: CorpusDocument, chunk_size: int = 500, chunk_overlap: int = 80
) -> list[Chunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be non-negative")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    text = (doc.text or "").strip()
    spans = token_spans(text)
    sections = detect_sections(text)
    windows = (
        _section_windows(text, spans, sections, chunk_size, chunk_overlap)
        if sections
        else []
    )
    if not windows:
        windows = _base_windows(text, spans, chunk_size, chunk_overlap)

    chunks: list[Chunk] = []
    for idx, (start, end, char_start, char_end, chunk_text, section) in enumerate(
        windows
    ):
        if section is None and sections:
            section = find_section_for_span(sections, char_start, char_end)
        metadata = dict(doc.metadata)
        metadata.update(
            {
                "chunk_index": idx,
                "chunk_token_start": start,
                "chunk_token_end": end,
                "chunk_char_start": char_start,
                "chunk_char_end": char_end,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
            }
        )
        metadata.update(_section_metadata(section, chunk_text))
        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}:chunk:{idx}",
                doc_id=doc.doc_id,
                csv_row_id=doc.csv_row_id,
                text=chunk_text,
                metadata=metadata,
            )
        )
    return chunks


def chunk_documents(
    docs: list[CorpusDocument], chunk_size: int = 500, chunk_overlap: int = 80
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in docs:
        chunks.extend(
            chunk_document(doc, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        )
    return chunks
