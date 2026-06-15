from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from rfp_rag.build_index import build_index
from rfp_rag.chunking import chunk_document
from rfp_rag.corpus import CorpusDocument
from rfp_rag.providers import build_embeddings
from rfp_rag.vector_index import load_vector_store, search


def _write_index_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
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
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_chunk_document_uses_doc_and_chunk_ids() -> None:
    doc = CorpusDocument(
        csv_row_id="007",
        doc_id="doc:007",
        text="첫 문단입니다. 둘째 문단입니다. " * 80,
        metadata={"project_name": "테스트", "issuer": "기관"},
    )

    chunks = chunk_document(doc, chunk_size=40, chunk_overlap=10)

    assert len(chunks) > 1
    assert chunks[0].chunk_id == "doc:007:chunk:0"
    assert chunks[0].doc_id == "doc:007"
    assert chunks[0].csv_row_id == "007"
    assert chunks[0].metadata["chunk_index"] == 0
    assert chunks[0].metadata["chunk_size"] == 40
    assert chunks[0].metadata["chunk_overlap"] == 10


def test_chunk_document_adds_section_metadata_and_requirement_ids() -> None:
    doc = CorpusDocument(
        csv_row_id="007",
        doc_id="doc:007",
        text="\n".join(
            [
                "[PAGE 3]",
                "Ⅳ",
                "제안안내 사항",
                "2",
                "제안서 평가방법",
                "REQ-101 평가 기준은 기술능력평가와 가격평가로 구성한다.",
            ]
        ),
        metadata={"project_name": "테스트", "issuer": "기관"},
    )

    chunks = chunk_document(doc, chunk_size=200, chunk_overlap=20)

    assert chunks[0].metadata["section_title"] == "제안서 평가방법"
    assert chunks[0].metadata["section_type"] == "evaluation_criteria"
    assert chunks[0].metadata["section_path"] == ["제안안내 사항", "제안서 평가방법"]
    assert chunks[0].metadata["section_page_start"] == 3
    assert chunks[0].metadata["requirement_ids"] == ["REQ-101"]


def test_chunk_document_preserves_unsectioned_preamble_and_footer() -> None:
    doc = CorpusDocument(
        csv_row_id="008",
        doc_id="doc:008",
        text="\n".join(
            [
                "입찰공고 일반 안내 문장",
                "Ⅰ",
                "사업 안내",
                "1",
                "사업개요",
                "섹션 본문",
                "첨부 서식은 별도 파일을 참조한다.",
            ]
        ),
        metadata={"project_name": "테스트", "issuer": "기관"},
    )

    chunks = chunk_document(doc, chunk_size=50, chunk_overlap=10)
    combined = "\n".join(chunk.text for chunk in chunks)

    assert "입찰공고 일반 안내 문장" in combined
    assert "첨부 서식은 별도 파일을 참조한다." in combined
    assert any(chunk.metadata["section_title"] == "사업개요" for chunk in chunks)


def test_build_index_writes_manifest_and_retrieves_reference_doc(
    tmp_path: Path, parsed_manifest_factory
) -> None:
    out = tmp_path / "index"
    parse_manifest = parsed_manifest_factory(Path("data/data_list.csv"))

    manifest = build_index(
        data_path=Path("data/data_list.csv"),
        files_path=Path("data/files"),
        out_dir=out,
        chunk_size=500,
        chunk_overlap=80,
        embedding_provider="fake",  # legacy alias, normalized to offline
        parse_manifest_path=parse_manifest,
    )

    saved = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert saved == manifest
    assert manifest["embedding_provider"] == "offline"
    assert manifest["text_source"] == "parsed"
    assert manifest["vector_backend"] == "qdrant_local"
    assert manifest["unique_docs"] == 100
    assert manifest["chunk_count"] > 0
    assert (out / "chunks.jsonl").exists()
    assert (out / "qdrant").is_dir()

    store = load_vector_store(
        out / "qdrant", build_embeddings("offline"), lane="offline"
    )
    results = search(store, "한영대학교 트랙운영 학사정보시스템 고도화", top_k=3)

    assert results
    # Hash embeddings lack the legacy exact-substring bonus, so assert top-3 (deterministic).
    reference = next((r for r in results if r.doc_id == "doc:000"), None)
    assert reference is not None
    assert reference.chunk_id.startswith("doc:000:chunk:")
    assert reference.score > 0


def test_build_index_creates_qdrant_collection_and_manifest(
    tmp_path: Path, parsed_manifest_factory
) -> None:
    out = tmp_path / "index"
    parse_manifest = parsed_manifest_factory(Path("data/data_list.csv"))
    manifest = build_index(
        data_path=Path("data/data_list.csv"),
        files_path=Path("data/files"),
        out_dir=out,
        chunk_size=500,
        chunk_overlap=80,
        embedding_provider="fake",  # alias for offline
        parse_manifest_path=parse_manifest,
    )

    assert manifest["embedding_provider"] == "offline"
    assert manifest["embedding_model"] == "lexical-hash-v1"
    assert manifest["vector_backend"] == "qdrant_local"
    assert (out / "qdrant").is_dir()
    assert (out / "manifest.json").exists()
    assert (out / "chunks.jsonl").exists()


def test_build_index_uses_parsed_manifest_text(tmp_path: Path) -> None:
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    (files_dir / "a.hwp").write_bytes(b"hwp")
    (files_dir / "b.hwp").write_bytes(b"hwp")
    csv_path = tmp_path / "data.csv"
    _write_index_csv(
        csv_path,
        [
            {
                "공고 번호": "1",
                "공고 차수": "0",
                "사업명": "A 사업",
                "사업 금액": "1000",
                "발주 기관": "기관A",
                "공개 일자": "",
                "입찰 참여 시작일": "",
                "입찰 참여 마감일": "",
                "사업 요약": "요약A",
                "파일형식": "hwp",
                "파일명": "a.hwp",
                "텍스트": "CSV A 본문",
            },
            {
                "공고 번호": "2",
                "공고 차수": "0",
                "사업명": "B 사업",
                "사업 금액": "2000",
                "발주 기관": "기관B",
                "공개 일자": "",
                "입찰 참여 시작일": "",
                "입찰 참여 마감일": "",
                "사업 요약": "요약B",
                "파일형식": "hwp",
                "파일명": "b.hwp",
                "텍스트": "CSV B 본문",
            },
        ],
    )
    parsed_dir = tmp_path / "parsed"
    text_dir = parsed_dir / "text"
    text_dir.mkdir(parents=True)
    parsed_text = text_dir / "doc_000.txt"
    parsed_text.write_text("PARSED A 원문 본문", encoding="utf-8")
    parsed_text_b = text_dir / "doc_001.txt"
    parsed_text_b.write_text("PARSED B 원문 본문", encoding="utf-8")
    parse_manifest = parsed_dir / "manifest.jsonl"
    parse_manifest.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "doc_id": "doc:000",
                        "parse_status": "parsed",
                        "parser_backend": "unhwp",
                        "text_path": str(parsed_text),
                        "content_source": "source_hwp_text",
                        "source_quality": "source_parsed",
                        "citation_level": "page",
                        "page_citation_available": True,
                        "page_text_path": str(
                            parsed_dir / "page_text" / "doc_000.jsonl"
                        ),
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "doc_id": "doc:001",
                        "parse_status": "parsed",
                        "parser_backend": "unhwp",
                        "text_path": str(parsed_text_b),
                        "content_source": "source_hwp_text",
                        "source_quality": "source_parsed",
                        "citation_level": "page",
                        "page_citation_available": True,
                        "error_reason": None,
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = build_index(
        data_path=csv_path,
        files_path=files_dir,
        out_dir=tmp_path / "index",
        chunk_size=100,
        chunk_overlap=20,
        embedding_provider="fake",
        parse_manifest_path=parse_manifest,
    )

    chunks = [
        json.loads(line)
        for line in (tmp_path / "index" / "chunks.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    by_doc = {chunk["doc_id"]: chunk for chunk in chunks}
    assert manifest["text_source"] == "parsed"
    assert manifest["index_text_source_counts"] == {"parsed": 2}
    assert by_doc["doc:000"]["text"] == "PARSED A 원문 본문"
    assert by_doc["doc:000"]["metadata"]["index_text_source"] == "parsed"
    assert by_doc["doc:000"]["metadata"]["source_parser_backend"] == "unhwp"
    assert by_doc["doc:000"]["metadata"]["source_content_source"] == "source_hwp_text"
    assert "section_title" in by_doc["doc:000"]["metadata"]
    assert by_doc["doc:001"]["text"] == "PARSED B 원문 본문"
    assert by_doc["doc:001"]["metadata"]["index_text_source"] == "parsed"
    assert by_doc["doc:001"]["metadata"]["source_parse_status"] == "parsed"


def test_build_index_parsed_mode_rejects_unparsed_document(tmp_path: Path) -> None:
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    (files_dir / "a.hwp").write_bytes(b"hwp")
    csv_path = tmp_path / "data.csv"
    _write_index_csv(
        csv_path,
        [
            {
                "공고 번호": "1",
                "공고 차수": "0",
                "사업명": "A 사업",
                "사업 금액": "1000",
                "발주 기관": "기관A",
                "공개 일자": "",
                "입찰 참여 시작일": "",
                "입찰 참여 마감일": "",
                "사업 요약": "요약A",
                "파일형식": "hwp",
                "파일명": "a.hwp",
                "텍스트": "CSV A 본문",
            }
        ],
    )
    parse_manifest = tmp_path / "manifest.jsonl"
    parse_manifest.write_text(
        json.dumps(
            {
                "doc_id": "doc:000",
                "parse_status": "parser_error",
                "parser_backend": "unhwp",
                "text_path": None,
                "error_reason": "boom",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="parsed source text unavailable for doc:000"):
        build_index(
            data_path=csv_path,
            files_path=files_dir,
            out_dir=tmp_path / "index",
            chunk_size=100,
            chunk_overlap=20,
            embedding_provider="fake",
            parse_manifest_path=parse_manifest,
        )


def test_build_index_requires_parse_manifest_for_source_text(tmp_path: Path) -> None:
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    (files_dir / "a.hwp").write_bytes(b"hwp")
    csv_path = tmp_path / "data.csv"
    _write_index_csv(
        csv_path,
        [
            {
                "공고 번호": "1",
                "공고 차수": "0",
                "사업명": "A 사업",
                "사업 금액": "1000",
                "발주 기관": "기관A",
                "공개 일자": "",
                "입찰 참여 시작일": "",
                "입찰 참여 마감일": "",
                "사업 요약": "요약A",
                "파일형식": "hwp",
                "파일명": "a.hwp",
                "텍스트": "CSV A 본문",
            }
        ],
    )

    with pytest.raises(FileNotFoundError, match="parse manifest not found"):
        build_index(
            data_path=csv_path,
            files_path=files_dir,
            out_dir=tmp_path / "index",
            chunk_size=100,
            chunk_overlap=20,
            embedding_provider="fake",
            parse_manifest_path=tmp_path / "missing_manifest.jsonl",
        )


def test_build_index_rejects_malformed_corpus_before_indexing(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad.csv"
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    fieldnames = [
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
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "공고 번호": "1",
                "공고 차수": "0",
                "사업명": "깨진 사업",
                "사업 금액": "",
                "발주 기관": "기관",
                "공개 일자": "",
                "입찰 참여 시작일": "",
                "입찰 참여 마감일": "",
                "사업 요약": "요약",
                "파일형식": "hwp",
                "파일명": "missing.hwp",
                "텍스트": "",
            }
        )

    with pytest.raises(ValueError, match="corpus inspection failed"):
        build_index(
            data_path=csv_path,
            files_path=files_dir,
            out_dir=tmp_path / "index",
            chunk_size=500,
            chunk_overlap=80,
            embedding_provider="fake",
        )


def test_build_index_rejects_empty_required_metadata(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad_metadata.csv"
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    (files_dir / "ok.hwp").write_text("raw", encoding="utf-8")
    fieldnames = [
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
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "공고 번호": "1",
                "공고 차수": "0",
                "사업명": "",
                "사업 금액": "",
                "발주 기관": "기관",
                "공개 일자": "",
                "입찰 참여 시작일": "",
                "입찰 참여 마감일": "",
                "사업 요약": "요약",
                "파일형식": "hwp",
                "파일명": "ok.hwp",
                "텍스트": "본문",
            }
        )

    with pytest.raises(ValueError, match="empty required values"):
        build_index(
            data_path=csv_path,
            files_path=files_dir,
            out_dir=tmp_path / "index",
            chunk_size=500,
            chunk_overlap=80,
            embedding_provider="fake",
        )
