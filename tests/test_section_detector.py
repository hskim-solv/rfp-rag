from __future__ import annotations

from rfp_rag.section_detector import detect_sections, find_section_for_span


def test_detect_sections_skips_toc_and_builds_section_paths() -> None:
    text = "\n".join(
        [
            "목   차",
            "Ⅰ. 사업 안내\t 1",
            "1. 사업개요\t 1",
            "[PAGE 1]",
            "Ⅰ",
            "사업 안내",
            "1",
            "사업개요",
            "□ 사 업 명 : 테스트",
            "[PAGE 2]",
            "Ⅳ",
            "제안안내 사항",
            "2",
            "제안서 평가방법",
            "평가 기준은 기술능력평가와 가격평가로 구성한다.",
        ]
    )

    sections = detect_sections(text)

    assert [section.title for section in sections] == [
        "사업 안내",
        "사업개요",
        "제안안내 사항",
        "제안서 평가방법",
    ]
    assert sections[1].section_path == ["사업 안내", "사업개요"]
    assert sections[1].section_type == "project_overview"
    assert sections[1].page_start == 1
    assert sections[3].section_path == ["제안안내 사항", "제안서 평가방법"]
    assert sections[3].section_type == "evaluation_criteria"
    assert sections[3].page_start == 2


def test_detect_sections_exits_toc_without_page_marker() -> None:
    text = "\n".join(
        [
            "목차",
            "Ⅰ. 사업 안내\t 1",
            "1. 사업개요\t 2",
            "Ⅰ",
            "사업 안내",
            "1",
            "사업개요",
            "실제 사업 개요 본문",
        ]
    )

    sections = detect_sections(text)

    assert [section.title for section in sections] == ["사업 안내", "사업개요"]


def test_detect_sections_ignores_cover_date_before_toc() -> None:
    text = "\n".join(
        [
            "2024년 특성화 맞춤형 교육환경 구축",
            "제안요청서",
            "2024. 10. 30",
            "",
            "목   차",
            "Ⅰ. 사업 안내\t 1",
            "1. 사업개요\t 1",
            "Ⅰ",
            "사업 안내",
            "1",
            "사업개요",
            "□ 사 업 명 : 테스트",
        ]
    )

    sections = detect_sections(text)

    assert [section.title for section in sections] == ["사업 안내", "사업개요"]
    assert all(section.title != "10" for section in sections)
    assert all(section.title != "10. 30" for section in sections)


def test_detect_sections_ignores_hyphenated_page_number_titles() -> None:
    text = "\n".join(
        [
            "Ⅰ",
            "사업 안내",
            "1",
            "사업개요",
            "정상 본문",
            "45",
            "- 45 -",
            "다음 본문",
        ]
    )

    sections = detect_sections(text)

    assert [section.title for section in sections] == ["사업 안내", "사업개요"]


def test_find_section_for_span_uses_largest_overlap() -> None:
    text = "Ⅰ\n사업 안내\n본문 A\nⅡ\n제안안내 사항\n본문 B 평가 기준"
    sections = detect_sections(text)
    start = text.index("평가")
    end = len(text)

    selected = find_section_for_span(sections, start, end)

    assert selected is not None
    assert selected.title == "제안안내 사항"
    assert selected.section_type == "evaluation_criteria"
