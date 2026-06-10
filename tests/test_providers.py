from __future__ import annotations

import math

from rfp_rag.providers import LexicalHashEmbeddings


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def test_lexical_hash_embeddings_are_deterministic_and_unit_norm() -> None:
    emb = LexicalHashEmbeddings(dim=512)

    v1 = emb.embed_query("한영대학교 트랙운영 학사정보시스템 고도화")
    v2 = emb.embed_query("한영대학교 트랙운영 학사정보시스템 고도화")

    assert len(v1) == 512
    assert v1 == v2
    assert abs(math.sqrt(sum(x * x for x in v1)) - 1.0) < 1e-6


def test_related_text_scores_higher_than_unrelated() -> None:
    emb = LexicalHashEmbeddings(dim=512)

    doc = emb.embed_query("한영대학교 트랙운영 학사정보시스템 고도화 사업 제안요청서")
    related = emb.embed_query("한영대학교 학사정보시스템 사업 요약해줘")
    unrelated = emb.embed_query("화성 이주선 산소탱크 발사일은 언제야?")

    assert _cosine(doc, related) > _cosine(doc, unrelated)
    assert _cosine(doc, unrelated) < 0.25


def test_embed_documents_matches_embed_query() -> None:
    emb = LexicalHashEmbeddings(dim=256)

    docs = emb.embed_documents(["입찰 공고", "사업 요약"])

    assert len(docs) == 2
    assert docs[0] == emb.embed_query("입찰 공고")
