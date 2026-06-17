from __future__ import annotations

import re
from dataclasses import dataclass

_PAGE_RE = re.compile(r"^\[PAGE\s+(\d+)\]$")
_ROMAN_ONLY_RE = re.compile(r"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+$")
_NUMBER_ONLY_RE = re.compile(r"^\d+(?:[.)])?$")
_PAGE_NUMBER_TITLE_RE = re.compile(r"^(?:-+\s*|-?\s*\d+\s*-?)$")
_DIRECT_ROMAN_RE = re.compile(r"^([ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+)[.)]\s*(.+)$")
_DIRECT_NUMBER_RE = re.compile(r"^(\d+)[.)]\s*(.+)$")
_DATE_LINE_RE = re.compile(
    r"^\d{4}(?:\.\s*\d{1,2}(?:\.\s*\d{1,2})?\.?|년\s*\d{1,2}월(?:\s*\d{1,2}일)?)$"
)
_TITLE_HAS_LETTER_RE = re.compile(r"[A-Za-z가-힣]")
_TRAILING_PAGE_REF_RE = re.compile(r"(?:\t| {2,}|\s+\.{2,}\s*)\s*\d+\s*$")
_REQUIREMENT_ID_RE = re.compile(r"\b[A-Z]{2,8}[-_]\d{1,5}\b")


@dataclass(frozen=True)
class SectionSpan:
    title: str
    section_type: str
    section_path: list[str]
    level: int
    index: int
    char_start: int
    body_start: int
    char_end: int
    page_start: int | None
    page_end: int | None


@dataclass(frozen=True)
class _Line:
    raw: str
    stripped: str
    start: int
    end: int
    page: int | None


@dataclass(frozen=True)
class _HeadingCandidate:
    title: str
    level: int
    char_start: int
    body_start: int
    page_start: int | None


def extract_requirement_ids(text: str) -> list[str]:
    """Return stable, de-duplicated requirement identifiers found in a chunk."""
    seen: set[str] = set()
    ids: list[str] = []
    for match in _REQUIREMENT_ID_RE.finditer(text or ""):
        value = match.group(0)
        if value not in seen:
            seen.add(value)
            ids.append(value)
    return ids


def detect_sections(text: str) -> list[SectionSpan]:
    """Detect coarse RFP section spans from common Korean heading shapes.

    The detector intentionally stays heuristic: it recognizes TOC/page markers,
    paired headings such as ``Ⅳ`` + ``제안안내 사항`` and ``2`` + ``제안서 평가방법``,
    plus compact headings like ``1. 사업개요``. Page numbers are best-effort and
    are present only when the parsed text contains explicit ``[PAGE n]`` markers.
    """
    lines = _lines(text)
    candidates = _heading_candidates(lines)
    if not candidates:
        return []

    stack: list[tuple[int, str]] = []
    paths: list[list[str]] = []
    for candidate in candidates:
        while stack and stack[-1][0] >= candidate.level:
            stack.pop()
        path = [title for _, title in stack] + [candidate.title]
        paths.append(path)
        stack.append((candidate.level, candidate.title))

    sections: list[SectionSpan] = []
    for index, candidate in enumerate(candidates):
        char_end = (
            candidates[index + 1].char_start
            if index + 1 < len(candidates)
            else len(text)
        )
        body = text[candidate.body_start : char_end]
        page_end = _page_at(lines, max(candidate.char_start, char_end - 1))
        sections.append(
            SectionSpan(
                title=candidate.title,
                section_type=_classify_section(paths[index], body),
                section_path=paths[index],
                level=candidate.level,
                index=index,
                char_start=candidate.char_start,
                body_start=candidate.body_start,
                char_end=char_end,
                page_start=candidate.page_start,
                page_end=page_end,
            )
        )
    return sections


def find_section_for_span(
    sections: list[SectionSpan], char_start: int, char_end: int
) -> SectionSpan | None:
    """Return the most specific detected section overlapping a character span."""
    best: tuple[int, int, int, SectionSpan] | None = None
    for section in sections:
        overlap = min(char_end, section.char_end) - max(char_start, section.char_start)
        if overlap <= 0:
            continue
        # Prefer larger overlap, then deeper headings, then later headings. The
        # depth tie-break makes follow-up spans inside child sections resolve to
        # the leaf section even when a parent has the same overlap.
        candidate = (overlap, section.level, section.index, section)
        if best is None or candidate[:3] > best[:3]:
            best = candidate
    return best[3] if best else None


def _lines(text: str) -> list[_Line]:
    lines: list[_Line] = []
    page: int | None = None
    offset = 0
    for raw in text.splitlines(keepends=True):
        line_text = raw.rstrip("\r\n")
        stripped = line_text.strip()
        marker = _PAGE_RE.match(stripped)
        if marker:
            page = int(marker.group(1))
        lines.append(
            _Line(
                raw=line_text,
                stripped=stripped,
                start=offset,
                end=offset + len(line_text),
                page=page,
            )
        )
        offset += len(raw)
    return lines


def _heading_candidates(lines: list[_Line]) -> list[_HeadingCandidate]:
    candidates: list[_HeadingCandidate] = []
    in_toc = False
    consumed: set[int] = set()

    for idx, line in enumerate(lines):
        if idx in consumed or not line.stripped:
            continue
        if "목 차" in line.stripped or line.stripped.replace(" ", "") == "목차":
            in_toc = True
            continue
        if _PAGE_RE.match(line.stripped):
            in_toc = False
            continue
        if in_toc:
            if _looks_like_toc_entry(line.stripped):
                continue
            if (
                _paired_heading(lines, idx) is not None
                or _direct_heading(line) is not None
            ):
                in_toc = False
            else:
                continue
        if _looks_like_toc_entry(line.stripped):
            continue

        paired = _paired_heading(lines, idx)
        if paired is not None:
            candidates.append(paired)
            consumed.add(idx)
            consumed.add(_next_content_line_index(lines, idx + 1) or idx)
            continue

        direct = _direct_heading(line)
        if direct is not None:
            candidates.append(direct)

    return candidates


def _paired_heading(lines: list[_Line], idx: int) -> _HeadingCandidate | None:
    line = lines[idx]
    level: int | None = None
    if _ROMAN_ONLY_RE.match(line.stripped):
        level = 1
    elif _NUMBER_ONLY_RE.match(line.stripped):
        level = 2
    if level is None:
        return None

    title_idx = _next_content_line_index(lines, idx + 1)
    if title_idx is None:
        return None
    title_line = lines[title_idx]
    if _PAGE_RE.match(title_line.stripped):
        return None
    if _ROMAN_ONLY_RE.match(title_line.stripped) or _NUMBER_ONLY_RE.match(
        title_line.stripped
    ):
        return None
    if _looks_like_toc_entry(title_line.stripped):
        return None
    title = _clean_title(title_line.stripped)
    if not _is_plausible_title(title):
        return None
    return _HeadingCandidate(
        title=title,
        level=level,
        char_start=line.start,
        body_start=title_line.end,
        page_start=line.page or title_line.page,
    )


def _direct_heading(line: _Line) -> _HeadingCandidate | None:
    if _DATE_LINE_RE.match(line.stripped):
        return None
    match = _DIRECT_ROMAN_RE.match(line.stripped)
    level = 1
    if match is None:
        match = _DIRECT_NUMBER_RE.match(line.stripped)
        level = 2
    if match is None:
        return None
    title = _clean_title(match.group(2))
    if _looks_like_toc_entry(line.stripped) or not _is_plausible_title(title):
        return None
    return _HeadingCandidate(
        title=title,
        level=level,
        char_start=line.start,
        body_start=line.end,
        page_start=line.page,
    )


def _next_content_line_index(lines: list[_Line], start: int) -> int | None:
    for idx in range(start, len(lines)):
        if lines[idx].stripped and not _PAGE_RE.match(lines[idx].stripped):
            return idx
    return None


def _looks_like_toc_entry(line: str) -> bool:
    return bool(_TRAILING_PAGE_REF_RE.search(line))


def _clean_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip(" .\t")


def _is_plausible_title(title: str) -> bool:
    if not title or len(title) > 80:
        return False
    if not _TITLE_HAS_LETTER_RE.search(title):
        return False
    if (
        title.isdigit()
        or _PAGE_NUMBER_TITLE_RE.match(title)
        or _DATE_LINE_RE.match(title)
    ):
        return False
    if title.endswith(("다", "요", "함")) and len(title) > 20:
        return False
    return True


def _classify_section(section_path: list[str], body: str) -> str:
    haystack = f"{' '.join(section_path)}\n{body[:1500]}"
    if any(term in haystack for term in ("보안", "개인정보", "암호화")):
        return "security"
    if any(
        term in haystack for term in ("평가", "배점", "심사", "정량평가", "정성평가")
    ):
        return "evaluation_criteria"
    if any(term in haystack for term in ("제출", "접수", "제안서 작성", "제안안내")):
        return "submission"
    if any(term in haystack for term in ("참가자격", "입찰참가", "입찰 참가", "자격")):
        return "eligibility"
    if any(term in haystack for term in ("요구", "과업", "구축범위", "기능", "세부")):
        return "requirements"
    if any(
        term in haystack
        for term in ("사업개요", "사업 안내", "개요", "추진배경", "목적")
    ):
        return "project_overview"
    if any(term in haystack for term in ("계약", "납품", "산출물")):
        return "contract"
    return "general"


def _page_at(lines: list[_Line], offset: int) -> int | None:
    page: int | None = None
    for line in lines:
        if line.start > offset:
            break
        if line.page is not None:
            page = line.page
    return page
