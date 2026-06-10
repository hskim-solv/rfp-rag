# Real Provider 품질 레인 (LangChain) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** OpenAI + Qdrant + RAGAS 기반 real RAG 레인을 LangChain 인터페이스 통합 구조로 구축하여 `rag_quality_complete` 게이트를 판정 가능하게 만든다.

**Architecture:** 단일 LangChain 파이프라인에 offline/real 두 레인이 구현체 주입으로 갈라진다. offline 레인은 커스텀 `LexicalHashEmbeddings` + 템플릿 생성기로 API 키 없이 전체 재현(pytest/CI 기본 레인), real 레인은 `OpenAIEmbeddings` + `ChatOpenAI`(structured output) + RAGAS judge. 청킹·chunk ID 규칙·55건 평가 세트·메트릭 정의는 기존 자산을 그대로 보존한다.

**Tech Stack:** Python 3.11, langchain-core 1.x(설치됨 1.3.3), langchain-openai(신규), langchain-qdrant(신규), qdrant-client(설치됨 1.18.0, 로컬 모드), ragas(신규), pytest

**Spec:** `docs/superpowers/specs/2026-06-10-real-provider-quality-lane-design.md`

**레인 식별자(전역 통일):** `offline` | `real_openai`. 기존 CLI 값 `fake`(build), `fake_offline`(evaluate)은 하위 호환 별칭. 아티팩트에는 통일 식별자만 기록.

**모델 기본값(환경변수로 교체 가능):**
- 임베딩 `RFP_EMBEDDING_MODEL` 기본 `text-embedding-3-small` (1536차원, $0.02/1M)
- 생성 `RFP_GENERATION_MODEL` 기본 `gpt-5.4-mini` ($0.75/$4.5 per 1M)
- judge `RFP_JUDGE_MODEL` 기본 `gpt-5.4` ($2.5/$15 per 1M)
- 1회 풀 사이클 비용 추정: 인덱싱 ~$0.02 + 평가 ~$0.3 + judge ~$2-4 (judge를 gpt-5.4-mini로 낮추면 총 ~$1)

---

## 사전 참고: 기존 코드 계약 (모든 태스크 공통)

- `Chunk` (rfp_rag/chunking.py): `chunk_id`(`doc:{row}:chunk:{n}`), `doc_id`, `csv_row_id`, `text`, `metadata`
- `SearchResult` (rfp_rag/index_store.py): `chunk_id, doc_id, csv_row_id, score, text, metadata` (frozen dataclass)
- 응답 JSON 스키마 (rfp_rag/ask.py가 반환, 평가가 소비 — **기존 키 제거·의미 변경 금지, 키 추가는 허용**):
  `{"query", "answer", "sources": [{"doc_id","chunk_id","score","csv_row_id","project_name","issuer","filename"}], "warnings", "confidence", "retrieved_doc_ids", "retrieved_chunk_ids", "scores"}`
  (이 계획에서 `source_texts` 키가 추가된다 — Task 11 (d) 참조)
- abstention 계약: answer에 `"없는 정보"` 포함 + warnings에 `"insufficient_context"` + confidence `"low"` + sources `[]`
- 메타데이터 키: `project_name`, `issuer`, `summary`, `budget_krw_int`, `bid_end_at_iso`, `bid_end_at_raw`, `csv_filename_raw`
- 실행 명령은 항상 저장소 루트(`/Users/hskim/Desktop/projects/RFP`)에서 `python3 -m pytest ...` 형태로 실행

---

### Task 1: 의존성 설치 + pytest marker 등록

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 패키지 설치**

```bash
pip3 install langchain-openai langchain-qdrant ragas
```

설치 후 버전 확인:

```bash
pip3 list | grep -iE "langchain-openai|langchain-qdrant|ragas"
```

Expected: 세 패키지 모두 출력 (버전은 설치 시점 최신)

- [ ] **Step 2: pyproject.toml에 의존성·marker 추가**

`pyproject.toml` 전체를 다음으로 교체 (버전 핀은 Step 1에서 확인된 실제 설치 버전의 minor로 기입):

```toml
[project]
name = "rfp-rag"
version = "0.2.0"
description = "CSV-first RFP RAG baseline with LangChain real provider quality lane"
requires-python = ">=3.11"
dependencies = [
    "langchain-core>=1.3",
    "langchain-openai",
    "langchain-qdrant",
    "qdrant-client>=1.18",
    "ragas",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
markers = [
    "real: requires OPENAI_API_KEY and network access (deselect with '-m \"not real\"')",
]
```

- [ ] **Step 3: 기존 테스트가 여전히 통과하는지 확인**

Run: `python3 -m pytest -q`
Expected: 전체 PASS (기존 테스트 영향 없음)

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add langchain-openai/langchain-qdrant/ragas deps and real marker"
```

---

### Task 2: LexicalHashEmbeddings — offline 임베딩 (LangChain Embeddings 구현체)

**Files:**
- Create: `rfp_rag/providers.py`
- Test: `tests/test_providers.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_providers.py` 생성:

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_providers.py -v`
Expected: FAIL — `ModuleNotFoundError` 또는 `ImportError: cannot import name 'LexicalHashEmbeddings'`

- [ ] **Step 3: 구현**

`rfp_rag/providers.py` 생성:

```python
from __future__ import annotations

import hashlib
import math

from langchain_core.embeddings import Embeddings

from .fake_provider import lexical_features


class LexicalHashEmbeddings(Embeddings):
    """Deterministic offline embeddings: hashed Korean n-gram lexical features.

    Cosine similarity approximates the legacy fake lexical retrieval, so the
    offline lane keeps meaningful retrieval/abstention behavior without API keys.
    """

    def __init__(self, dim: int = 4096) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for feature, weight in lexical_features(text).items():
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign * float(weight)
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            vec[0] = 1.0
            return vec
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_providers.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/providers.py tests/test_providers.py
git commit -m "feat: add deterministic LexicalHashEmbeddings for offline lane"
```

---

### Task 3: AnswerGenerator 인터페이스 + TemplateAnswerGenerator (offline 생성)

**Files:**
- Modify: `rfp_rag/providers.py` (Task 2에서 생성한 파일에 추가)
- Test: `tests/test_providers.py` (추가)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_providers.py`에 추가:

```python
from rfp_rag.index_store import SearchResult
from rfp_rag.providers import TemplateAnswerGenerator


def _result(score: float = 0.8) -> SearchResult:
    return SearchResult(
        chunk_id="doc:000:chunk:0",
        doc_id="doc:000",
        csv_row_id="000",
        score=score,
        text="트랙운영 학사정보시스템 고도화 본문",
        metadata={
            "project_name": "한영대학교 트랙운영 학사정보시스템 고도화",
            "issuer": "한영대학",
            "summary": "학사정보시스템을 고도화한다.",
            "budget_krw_int": 150000000,
            "bid_end_at_iso": "2024-05-01T10:00:00",
        },
    )


def test_template_generator_answers_budget_from_metadata() -> None:
    gen = TemplateAnswerGenerator()

    answer = gen.generate("한영대학교 사업 금액은 얼마야?", [_result()])

    assert "150,000,000" in answer
    assert "없는 정보" not in answer


def test_template_generator_falls_back_to_context_answer() -> None:
    gen = TemplateAnswerGenerator()

    answer = gen.generate("이 사업의 추진 배경 알려줘", [_result()])

    assert "한영대학교 트랙운영 학사정보시스템 고도화" in answer
    assert "한영대학" in answer
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_providers.py -v`
Expected: 새 테스트 2개 FAIL — `ImportError: cannot import name 'TemplateAnswerGenerator'`

- [ ] **Step 3: 구현** — `rfp_rag/providers.py` 끝에 추가 (기존 `ask.py`의 `_metadata_answer`/`_context_answer` 로직 이식):

```python
from typing import Protocol

from .index_store import SearchResult


class AnswerGenerator(Protocol):
    """Generates the answer string for a query given retrieved chunks."""

    def generate(self, query: str, results: list[SearchResult]) -> str: ...


class TemplateAnswerGenerator:
    """Offline deterministic generator: metadata template with context fallback."""

    def generate(self, query: str, results: list[SearchResult]) -> str:
        top = results[0]
        return self._metadata_answer(query, top) or self._context_answer(top)

    @staticmethod
    def _metadata_answer(query: str, top: SearchResult) -> str | None:
        md = top.metadata
        query_text = query or ""
        project = md.get("project_name", "해당 사업")
        if "예산" in query_text or "금액" in query_text or "사업비" in query_text:
            value = md.get("budget_krw_int")
            if value is not None:
                return f"{project}의 사업 금액은 {value:,}원입니다."
        if "마감" in query_text or "기한" in query_text or "입찰" in query_text:
            value = md.get("bid_end_at_iso") or md.get("bid_end_at_raw")
            if value:
                return f"{project}의 입찰 참여 마감일은 {value}입니다."
        if "발주" in query_text or "기관" in query_text:
            value = md.get("issuer")
            if value:
                return f"{project}의 발주 기관은 {value}입니다."
        if "요약" in query_text or "무엇" in query_text or "내용" in query_text:
            summary = (md.get("summary") or "").strip()
            if summary:
                return f"{project} 요약: {summary}"
        return None

    @staticmethod
    def _context_answer(top: SearchResult) -> str:
        md = top.metadata
        project = md.get("project_name", "검색된 사업")
        issuer = md.get("issuer", "발주기관 미상")
        summary = (md.get("summary") or "").strip()
        if summary:
            return f"검색된 근거 기준으로 {project}는 {issuer}의 사업이며, 주요 내용은 다음과 같습니다. {summary}"
        snippet = " ".join((top.text or "").split())[:350]
        return f"검색된 근거 기준으로 {project}는 {issuer}의 사업입니다. 관련 본문: {snippet}"
```

(import 문 `from typing import Protocol`과 `from .index_store import SearchResult`는 파일 상단 import 블록으로 이동)

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_providers.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/providers.py tests/test_providers.py
git commit -m "feat: add AnswerGenerator protocol and offline TemplateAnswerGenerator"
```

---

### Task 4: vector_index.py — Qdrant 빌드/로드 (chunk_id 보존)

**Files:**
- Create: `rfp_rag/vector_index.py`
- Test: `tests/test_vector_index.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_vector_index.py` 생성:

```python
from __future__ import annotations

from pathlib import Path

from rfp_rag.chunking import Chunk
from rfp_rag.providers import LexicalHashEmbeddings
from rfp_rag.vector_index import build_vector_store, load_vector_store, search


def _chunks() -> list[Chunk]:
    return [
        Chunk(
            chunk_id="doc:000:chunk:0",
            doc_id="doc:000",
            csv_row_id="000",
            text="한영대학교 트랙운영 학사정보시스템 고도화 사업 본문",
            metadata={"project_name": "한영대학교 트랙운영 학사정보시스템 고도화", "issuer": "한영대학"},
        ),
        Chunk(
            chunk_id="doc:001:chunk:0",
            doc_id="doc:001",
            csv_row_id="001",
            text="국립중앙도서관 자료보존 환경 개선 사업 본문",
            metadata={"project_name": "국립중앙도서관 자료보존 환경 개선", "issuer": "국립중앙도서관"},
        ),
    ]


def test_build_and_search_preserves_chunk_identity(tmp_path: Path) -> None:
    emb = LexicalHashEmbeddings(dim=512)
    store = build_vector_store(_chunks(), emb, qdrant_path=None, lane="offline")

    results = search(store, "한영대학교 학사정보시스템 사업", top_k=2)

    assert results[0].chunk_id == "doc:000:chunk:0"
    assert results[0].doc_id == "doc:000"
    assert results[0].csv_row_id == "000"
    assert results[0].metadata["issuer"] == "한영대학"
    assert results[0].score >= results[1].score
    assert "학사정보시스템" in results[0].text


def test_persist_and_reload_roundtrip(tmp_path: Path) -> None:
    emb = LexicalHashEmbeddings(dim=512)
    qdrant_path = tmp_path / "qdrant"
    store = build_vector_store(_chunks(), emb, qdrant_path=qdrant_path, lane="offline")
    del store

    reloaded = load_vector_store(qdrant_path, emb, lane="offline")
    results = search(reloaded, "국립중앙도서관 자료보존", top_k=1)

    assert results[0].chunk_id == "doc:001:chunk:0"


def test_search_returns_at_most_top_k(tmp_path: Path) -> None:
    emb = LexicalHashEmbeddings(dim=512)
    store = build_vector_store(_chunks(), emb, qdrant_path=None, lane="offline")

    assert len(search(store, "사업", top_k=1)) == 1
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_vector_index.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rfp_rag.vector_index'`

- [ ] **Step 3: 구현**

`rfp_rag/vector_index.py` 생성:

```python
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from .chunking import Chunk
from .index_store import SearchResult

_COLLECTION_PREFIX = "rfp_chunks"


def collection_name(lane: str) -> str:
    return f"{_COLLECTION_PREFIX}_{lane}"


def embedding_text(chunk: Chunk) -> str:
    """Prepend key metadata so metadata-style questions retrieve well."""
    md = chunk.metadata
    header = f"사업명: {md.get('project_name', '')}\n발주기관: {md.get('issuer', '')}"
    return f"{header}\n{chunk.text}" if chunk.text else header


def chunk_to_document(chunk: Chunk) -> Document:
    metadata = dict(chunk.metadata)
    metadata.update(
        {
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "csv_row_id": chunk.csv_row_id,
        }
    )
    return Document(page_content=embedding_text(chunk), metadata=metadata)


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def _client(qdrant_path: Path | None) -> QdrantClient:
    if qdrant_path is None:
        return QdrantClient(":memory:")
    return QdrantClient(path=str(qdrant_path))


def build_vector_store(
    chunks: list[Chunk],
    embeddings: Embeddings,
    qdrant_path: Path | None,
    lane: str,
) -> QdrantVectorStore:
    """Create a fresh collection and index all chunks. Wipes existing path data."""
    if qdrant_path is not None and qdrant_path.exists():
        shutil.rmtree(qdrant_path)
    client = _client(qdrant_path)
    dim = len(embeddings.embed_query("차원 측정용 텍스트"))
    client.create_collection(
        collection_name=collection_name(lane),
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    store = QdrantVectorStore(
        client=client,
        collection_name=collection_name(lane),
        embedding=embeddings,
    )
    documents = [chunk_to_document(chunk) for chunk in chunks]
    ids = [_point_id(chunk.chunk_id) for chunk in chunks]
    store.add_documents(documents=documents, ids=ids)
    return store


def load_vector_store(qdrant_path: Path, embeddings: Embeddings, lane: str) -> QdrantVectorStore:
    client = _client(qdrant_path)
    return QdrantVectorStore(
        client=client,
        collection_name=collection_name(lane),
        embedding=embeddings,
    )


def search(store: QdrantVectorStore, query: str, top_k: int = 5) -> list[SearchResult]:
    if top_k <= 0:
        return []
    pairs = store.similarity_search_with_score(query, k=top_k)
    results: list[SearchResult] = []
    for document, score in pairs:
        md = dict(document.metadata)
        results.append(
            SearchResult(
                chunk_id=md.pop("chunk_id"),
                doc_id=md.pop("doc_id"),
                csv_row_id=md.pop("csv_row_id"),
                score=round(float(score), 8),
                text=document.page_content,
                metadata=md,
            )
        )
    results.sort(key=lambda item: (-item.score, item.doc_id, item.chunk_id))
    return results
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_vector_index.py -v`
Expected: 3 PASS

참고: langchain-qdrant가 metadata를 payload 하위 키(`metadata`)에 중첩 저장하더라도 `Document.metadata`로 복원해 주므로 위 코드는 그대로 동작한다. 만약 `md.pop("chunk_id")`에서 KeyError가 나면 `document.metadata` 구조를 `print`로 확인하고 중첩 키를 평탄화할 것.

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/vector_index.py tests/test_vector_index.py
git commit -m "feat: add Qdrant vector index with chunk identity preservation"
```

---

### Task 5: rag_chain.py — 검색→abstention→생성 통합 (offline 레인 기준)

**Files:**
- Create: `rfp_rag/rag_chain.py`
- Test: `tests/test_rag_chain.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_rag_chain.py` 생성:

```python
from __future__ import annotations

from rfp_rag.chunking import Chunk
from rfp_rag.providers import LexicalHashEmbeddings, TemplateAnswerGenerator
from rfp_rag.rag_chain import answer_with_store
from rfp_rag.vector_index import build_vector_store


def _store():
    chunks = [
        Chunk(
            chunk_id="doc:000:chunk:0",
            doc_id="doc:000",
            csv_row_id="000",
            text="한영대학교 트랙운영 학사정보시스템 고도화 사업 제안요청서 본문",
            metadata={
                "project_name": "한영대학교 트랙운영 학사정보시스템 고도화",
                "issuer": "한영대학",
                "summary": "학사정보시스템 고도화 사업",
                "csv_filename_raw": "han.hwp",
            },
        )
    ]
    return build_vector_store(chunks, LexicalHashEmbeddings(dim=512), qdrant_path=None, lane="offline")


def test_in_domain_question_returns_cited_answer() -> None:
    response = answer_with_store(
        _store(),
        TemplateAnswerGenerator(),
        "한영대학교 트랙운영 학사정보시스템 고도화 사업을 요약해줘",
        top_k=3,
        min_score=0.05,
    )

    assert response["answer"]
    assert "없는 정보" not in response["answer"]
    assert response["sources"][0]["chunk_id"] == "doc:000:chunk:0"
    assert response["sources"][0]["chunk_id"] in response["retrieved_chunk_ids"]
    assert response["warnings"] == []
    assert response["confidence"] in {"medium", "high"}


def test_unrelated_question_abstains() -> None:
    response = answer_with_store(
        _store(),
        TemplateAnswerGenerator(),
        "화성 이주선 산소탱크 발사일은 언제야?",
        top_k=3,
        min_score=0.05,
    )

    assert "없는 정보" in response["answer"]
    assert "insufficient_context" in response["warnings"]
    assert response["confidence"] == "low"
    assert response["sources"] == []
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_rag_chain.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rfp_rag.rag_chain'`

- [ ] **Step 3: 구현**

`rfp_rag/rag_chain.py` 생성:

```python
from __future__ import annotations

from typing import Any

from langchain_qdrant import QdrantVectorStore

from .index_store import SearchResult
from .providers import AnswerGenerator
from .vector_index import search

ABSTAIN_ANSWER = "검색된 제안요청서 근거만으로는 답할 수 없는 정보입니다. 없는 정보"


def _source_from_result(result: SearchResult) -> dict[str, Any]:
    md = result.metadata
    return {
        "doc_id": result.doc_id,
        "chunk_id": result.chunk_id,
        "score": result.score,
        "csv_row_id": result.csv_row_id,
        "project_name": md.get("project_name", ""),
        "issuer": md.get("issuer", ""),
        "filename": md.get("csv_filename_raw", ""),
    }


def abstention_response(query: str, results: list[SearchResult]) -> dict[str, Any]:
    return {
        "query": query,
        "answer": ABSTAIN_ANSWER,
        "sources": [],
        "warnings": ["insufficient_context"],
        "confidence": "low",
        "retrieved_doc_ids": [r.doc_id for r in results],
        "retrieved_chunk_ids": [r.chunk_id for r in results],
        "scores": [r.score for r in results],
    }


def answer_with_store(
    store: QdrantVectorStore,
    generator: AnswerGenerator,
    query: str,
    top_k: int = 5,
    min_score: float = 0.05,
) -> dict[str, Any]:
    results = search(store, query, top_k=top_k)
    if not results or results[0].score < min_score:
        return abstention_response(query, results)

    answer = generator.generate(query, results)
    if "없는 정보" in answer:
        return abstention_response(query, results)

    top_score = results[0].score
    return {
        "query": query,
        "answer": answer,
        "sources": [_source_from_result(r) for r in results],
        "warnings": [],
        "confidence": "high" if top_score >= 2 * min_score else "medium",
        "retrieved_doc_ids": [r.doc_id for r in results],
        "retrieved_chunk_ids": [r.chunk_id for r in results],
        "scores": [r.score for r in results],
    }
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_rag_chain.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/rag_chain.py tests/test_rag_chain.py
git commit -m "feat: add rag_chain combining retrieval, abstention gate, and generation"
```

---

### Task 6: LLMAnswerGenerator — real 생성 (structured output + 인용 검증)

**Files:**
- Modify: `rfp_rag/providers.py`
- Test: `tests/test_providers.py` (추가)

설계: LLM 호출부(`_invoke`)와 순수 로직(프롬프트 구성, 인용 검증)을 분리한다. 단위 테스트는 `_invoke`를 스텁으로 대체해 API 키 없이 검증하고, 실제 호출은 Task 12의 real 스모크가 담당한다.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_providers.py`에 추가:

```python
from rfp_rag.providers import LLMAnswer, LLMAnswerGenerator, build_answer_prompt


def test_build_answer_prompt_labels_chunks_and_includes_query() -> None:
    prompt = build_answer_prompt("발주 기관은 어디야?", [_result()])

    assert "[doc:000:chunk:0]" in prompt
    assert "발주 기관은 어디야?" in prompt
    assert "트랙운영 학사정보시스템 고도화 본문" in prompt


def test_llm_generator_keeps_only_valid_citations() -> None:
    def fake_invoke(prompt: str) -> LLMAnswer:
        return LLMAnswer(
            answer="발주 기관은 한영대학입니다.",
            cited_chunk_ids=["doc:000:chunk:0", "doc:999:chunk:9"],
            insufficient_context=False,
        )

    gen = LLMAnswerGenerator(invoke=fake_invoke)

    answer = gen.generate("발주 기관은 어디야?", [_result()])

    assert answer == "발주 기관은 한영대학입니다."
    assert gen.last_cited_chunk_ids == ["doc:000:chunk:0"]


def test_llm_generator_signals_abstention_via_phrase() -> None:
    def fake_invoke(prompt: str) -> LLMAnswer:
        return LLMAnswer(answer="자료가 없습니다.", cited_chunk_ids=[], insufficient_context=True)

    gen = LLMAnswerGenerator(invoke=fake_invoke)

    answer = gen.generate("화성 기지 예산은?", [_result()])

    assert "없는 정보" in answer
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_providers.py -v`
Expected: 새 테스트 3개 FAIL — `ImportError`

- [ ] **Step 3: 구현** — `rfp_rag/providers.py`에 추가:

```python
import os
from typing import Callable

from pydantic import BaseModel, Field

SYSTEM_PROMPT = (
    "당신은 B2G 입찰지원 컨설팅 '입찰메이트'의 RFP 분석 어시스턴트입니다. "
    "반드시 아래 제공된 근거 chunk 내용만 사용해 한국어로 답하세요. "
    "모든 답변은 근거가 된 chunk id를 cited_chunk_ids에 담으세요. "
    "근거가 부족하면 insufficient_context를 true로 하고 answer에 '없는 정보'를 포함하세요. "
    "금액·날짜·기관명은 근거 원문 표기 그대로 인용하세요."
)


class LLMAnswer(BaseModel):
    answer: str = Field(description="근거 기반 한국어 답변")
    cited_chunk_ids: list[str] = Field(default_factory=list, description="답변 근거 chunk id 목록")
    insufficient_context: bool = Field(default=False, description="근거 부족 여부")


def build_answer_prompt(query: str, results: list[SearchResult]) -> str:
    blocks = []
    for r in results:
        blocks.append(f"[{r.chunk_id}] (사업명: {r.metadata.get('project_name', '')})\n{r.text}")
    context = "\n\n".join(blocks)
    return f"근거 chunk 목록:\n\n{context}\n\n질문: {query}"


def _default_invoke(prompt: str) -> LLMAnswer:
    from langchain_openai import ChatOpenAI

    model = os.environ.get("RFP_GENERATION_MODEL", "gpt-5.4-mini")
    llm = ChatOpenAI(model=model).with_structured_output(LLMAnswer)
    return llm.invoke([("system", SYSTEM_PROMPT), ("human", prompt)])


class LLMAnswerGenerator:
    """Real lane generator: ChatOpenAI structured output with citation validation."""

    def __init__(self, invoke: Callable[[str], LLMAnswer] | None = None) -> None:
        self._invoke = invoke or _default_invoke
        self.last_cited_chunk_ids: list[str] = []

    def generate(self, query: str, results: list[SearchResult]) -> str:
        payload = self._invoke(build_answer_prompt(query, results))
        retrieved_ids = {r.chunk_id for r in results}
        self.last_cited_chunk_ids = [cid for cid in payload.cited_chunk_ids if cid in retrieved_ids]
        if payload.insufficient_context:
            answer = payload.answer or ""
            return answer if "없는 정보" in answer else f"{answer} 없는 정보".strip()
        return payload.answer
```

(import 문은 파일 상단 import 블록으로 이동: `import os`, `from typing import Callable, Protocol`, `from pydantic import BaseModel, Field`)

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_providers.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/providers.py tests/test_providers.py
git commit -m "feat: add LLMAnswerGenerator with structured output and citation validation"
```

---

### Task 7: 레인 팩토리 — provider 문자열 → 구현체 묶음

**Files:**
- Modify: `rfp_rag/providers.py`
- Test: `tests/test_providers.py` (추가)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_providers.py`에 추가:

```python
import pytest

from rfp_rag.providers import (
    LANE_OFFLINE,
    LANE_REAL_OPENAI,
    build_embeddings,
    normalize_lane,
)


def test_normalize_lane_accepts_aliases() -> None:
    assert normalize_lane("offline") == LANE_OFFLINE
    assert normalize_lane("fake") == LANE_OFFLINE
    assert normalize_lane("fake_offline") == LANE_OFFLINE
    assert normalize_lane("openai") == LANE_REAL_OPENAI
    assert normalize_lane("real_openai") == LANE_REAL_OPENAI


def test_normalize_lane_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unknown lane"):
        normalize_lane("cohere")


def test_build_embeddings_offline_is_lexical_hash() -> None:
    assert isinstance(build_embeddings(LANE_OFFLINE), LexicalHashEmbeddings)


def test_build_embeddings_real_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY required"):
        build_embeddings(LANE_REAL_OPENAI)
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_providers.py -v`
Expected: 새 테스트 4개 FAIL — `ImportError`

- [ ] **Step 3: 구현** — `rfp_rag/providers.py`에 추가:

```python
LANE_OFFLINE = "offline"
LANE_REAL_OPENAI = "real_openai"

_LANE_ALIASES = {
    "offline": LANE_OFFLINE,
    "fake": LANE_OFFLINE,
    "fake_offline": LANE_OFFLINE,
    "openai": LANE_REAL_OPENAI,
    "real_openai": LANE_REAL_OPENAI,
}

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


def normalize_lane(value: str) -> str:
    lane = _LANE_ALIASES.get((value or "").strip().lower())
    if lane is None:
        raise ValueError(f"unknown lane: {value!r} (expected one of {sorted(_LANE_ALIASES)})")
    return lane


def require_openai_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY required for real lane (offline lane runs without credentials)"
        )


def embedding_model_name(lane: str) -> str:
    if lane == LANE_OFFLINE:
        return "lexical-hash-v1"
    return os.environ.get("RFP_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def build_embeddings(lane: str):
    if lane == LANE_OFFLINE:
        return LexicalHashEmbeddings()
    require_openai_key()
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(model=embedding_model_name(lane))


def build_generator(lane: str) -> AnswerGenerator:
    if lane == LANE_OFFLINE:
        return TemplateAnswerGenerator()
    require_openai_key()
    return LLMAnswerGenerator()
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_providers.py -v`
Expected: 12 PASS

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/providers.py tests/test_providers.py
git commit -m "feat: add lane factory with aliases and API key guard"
```

---

### Task 8: build_index.py 전환 — Qdrant 인덱싱 + 레인 manifest

**Files:**
- Modify: `rfp_rag/build_index.py`
- Modify: `rfp_rag/index_store.py` (lexical retrieve 제거, 저장/타입 유지)
- Test: `tests/test_index.py` (기존 파일 업데이트)

- [ ] **Step 1: 기존 테스트 확인 후 업데이트**

먼저 기존 테스트를 읽는다: `tests/test_index.py`. 기존 단언(manifest 키, chunks.jsonl 존재 등)을 유지하면서 다음을 반영해 수정한다:

- `embedding_provider="fake"` 인자는 그대로 두되(별칭 동작 검증), manifest 단언을 `manifest["embedding_provider"] == "offline"`, `manifest["vector_backend"] == "qdrant_local"`로 변경
- Qdrant 디렉터리 생성 단언 추가

`tests/test_index.py`에 추가할 테스트:

```python
def test_build_index_creates_qdrant_collection_and_manifest(tmp_path: Path) -> None:
    out = tmp_path / "index"
    manifest = build_index(
        data_path=Path("data/data_list.csv"),
        files_path=Path("data/files"),
        out_dir=out,
        chunk_size=500,
        chunk_overlap=80,
        embedding_provider="fake",  # alias for offline
    )

    assert manifest["embedding_provider"] == "offline"
    assert manifest["embedding_model"] == "lexical-hash-v1"
    assert manifest["vector_backend"] == "qdrant_local"
    assert (out / "qdrant").is_dir()
    assert (out / "manifest.json").exists()
    assert (out / "chunks.jsonl").exists()
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_index.py -v`
Expected: 새 테스트 FAIL (`embedding_provider`가 `"fake"`로 기록되고 qdrant 디렉터리 없음)

- [ ] **Step 3: build_index.py 수정**

`rfp_rag/build_index.py`의 `build_index` 함수를 다음으로 교체 (검증·manifest 로직 유지, 인덱싱 경로 교체):

```python
from .providers import build_embeddings, embedding_model_name, normalize_lane
from .vector_index import build_vector_store


def build_index(
    data_path: Path | str,
    files_path: Path | str,
    out_dir: Path | str,
    chunk_size: int = 500,
    chunk_overlap: int = 80,
    embedding_provider: str = "offline",
) -> dict[str, Any]:
    lane = normalize_lane(embedding_provider)
    data_path = Path(data_path)
    files_path = Path(files_path)
    out_dir = Path(out_dir)
    corpus_manifest = inspect_corpus(data_path, files_path, None)
    _validate_corpus_manifest(corpus_manifest)
    docs = load_corpus(data_path, files_path)
    chunks = chunk_documents(docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    embeddings = build_embeddings(lane)
    build_vector_store(chunks, embeddings, qdrant_path=out_dir / "qdrant", lane=lane)

    manifest: dict[str, Any] = {
        "data_path": str(data_path),
        "files_path": str(files_path),
        "corpus_sha256": sha256_file(data_path),
        "corpus_row_count": corpus_manifest["row_count"],
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "embedding_provider": lane,
        "embedding_model": embedding_model_name(lane),
        "vector_backend": "qdrant_local",
        "chunk_count": len(chunks),
        "unique_docs": len({chunk.doc_id for chunk in chunks}),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_index(out_dir, manifest, chunks)
    return manifest
```

기존 `if embedding_provider != "fake": raise ValueError(...)` 가드와 argparse 기본값 `--embedding-provider`의 `default="fake"`를 `default="offline"`으로 변경.

- [ ] **Step 4: index_store.py에서 lexical retrieve 제거**

`rfp_rag/index_store.py`에서 `retrieve()`, `_search_text()` 함수와 `from .fake_provider import cosine_score, lexical_features, normalize_text` import를 삭제한다. `SearchResult`, `LocalIndex`, `chunk_to_record`, `chunk_from_record`, `save_index`, `load_index`는 유지.

`rfp_rag/fake_provider.py`에서 `cosine_score`를 삭제한다 (`lexical_features`, `normalize_text`는 LexicalHashEmbeddings가 사용하므로 유지).

- [ ] **Step 5: 이 태스크 범위의 테스트 통과 확인**

Run: `python3 -m pytest tests/test_index.py tests/test_providers.py tests/test_vector_index.py tests/test_rag_chain.py -v`
Expected: 전체 PASS

참고: `tests/test_qa.py`와 `tests/test_evaluate_report.py`는 `ask.py`가 아직 삭제된 lexical `retrieve`를 import하므로 이 시점에는 collection 에러가 난다 — Task 9/11에서 수정한다. 전체 `python3 -m pytest`는 Task 9 이후부터 다시 실행한다.

- [ ] **Step 6: Commit**

```bash
git add rfp_rag/build_index.py rfp_rag/index_store.py rfp_rag/fake_provider.py tests/test_index.py
git commit -m "feat: switch build_index to Qdrant lanes, retire lexical retrieve"
```

---

### Task 9: ask.py 전환 — rag_chain 경유, --provider 플래그

**Files:**
- Modify: `rfp_rag/ask.py` (대부분 교체)
- Modify: `rfp_rag/rag_chain.py` (`answer_query` 진입점 추가)
- Test: `tests/test_qa.py` (업데이트)

- [ ] **Step 1: 테스트 업데이트**

`tests/test_qa.py`의 `_index()`는 그대로 동작한다(`embedding_provider="fake"` 별칭). 기존 두 테스트의 단언은 응답 스키마가 동일하므로 그대로 유지된다. import만 변경:

```python
from rfp_rag.rag_chain import answer_query
```

(기존 `from rfp_rag.ask import answer_query` 대체. `rfp_rag.ask`는 CLI 셸로 유지되며 내부적으로 같은 함수를 호출.)

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_qa.py -v`
Expected: FAIL — `ImportError: cannot import name 'answer_query' from 'rfp_rag.rag_chain'`

- [ ] **Step 3: rag_chain.py에 진입점 추가**

`rfp_rag/rag_chain.py` 끝에 추가:

```python
import json
from pathlib import Path

from .providers import build_embeddings, build_generator, normalize_lane
from .vector_index import load_vector_store

DEFAULT_MIN_SCORE = 0.05


def _load_manifest(index_dir: Path) -> dict[str, Any]:
    manifest_path = index_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"index manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def answer_query(
    index_dir: Path | str,
    query: str,
    top_k: int = 5,
    min_score: float = DEFAULT_MIN_SCORE,
    provider: str | None = None,
) -> dict[str, Any]:
    index_dir = Path(index_dir)
    manifest = _load_manifest(index_dir)
    index_lane = normalize_lane(manifest.get("embedding_provider", "offline"))
    lane = normalize_lane(provider) if provider else index_lane
    if lane != index_lane:
        raise ValueError(
            f"provider lane {lane!r} does not match index embedding lane {index_lane!r}; rebuild the index"
        )
    embeddings = build_embeddings(lane)
    store = load_vector_store(index_dir / "qdrant", embeddings, lane=lane)
    generator = build_generator(lane)
    return answer_with_store(store, generator, query, top_k=top_k, min_score=min_score)
```

(import는 파일 상단으로 이동. `DEFAULT_MIN_SCORE = 0.05`는 lexical hash 코사인 분포 기준이며 real 레인 캘리브레이션은 Task 13에서 다룬다.)

- [ ] **Step 4: ask.py를 CLI 셸로 축소**

`rfp_rag/ask.py` 전체를 다음으로 교체:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .rag_chain import DEFAULT_MIN_SCORE, answer_query


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Answer a Korean RFP question from a local index with citations.")
    parser.add_argument("--index", required=True, type=Path, help="Index directory")
    parser.add_argument("--query", required=True, help="Question to answer")
    parser.add_argument("--top-k", default=5, type=int)
    parser.add_argument("--min-score", default=DEFAULT_MIN_SCORE, type=float)
    parser.add_argument("--provider", default=None, help="offline | real_openai (default: index lane)")
    parser.add_argument("--out", type=Path, help="Optional JSON output path")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    response = answer_query(
        args.index, args.query, top_k=args.top_k, min_score=args.min_score, provider=args.provider
    )
    payload = json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: 통과 확인 (evaluate 제외 전체)**

Run: `python3 -m pytest -q --ignore=tests/test_evaluate_report.py`
Expected: PASS (evaluate 테스트는 Task 11에서 수정)

Run: `python3 -m pytest tests/test_qa.py -v`
Expected: 2 PASS — in-domain 인용과 abstention이 Qdrant offline 레인에서 동작

- [ ] **Step 6: Commit**

```bash
git add rfp_rag/ask.py rfp_rag/rag_chain.py tests/test_qa.py
git commit -m "feat: route ask through rag_chain with lane-aware answer_query"
```

---

### Task 10: judge.py — RAGAS faithfulness/answer relevancy 래퍼

**Files:**
- Create: `rfp_rag/judge.py`
- Test: `tests/test_judge.py`

설계: RAGAS 메트릭 객체 생성(`_build_metrics`, API 키 필요)과 채점 루프(`judge_predictions`)를 분리한다. 단위 테스트는 스텁 메트릭을 주입한다. 채점 실패는 per-question `None` + warning으로 격리한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_judge.py` 생성:

```python
from __future__ import annotations

from rfp_rag.judge import judge_predictions


class _StubMetric:
    def __init__(self, name: str, score: float | Exception) -> None:
        self.name = name
        self._score = score

    async def single_turn_ascore(self, sample) -> float:
        if isinstance(self._score, Exception):
            raise self._score
        return self._score


def _prediction(query_type: str = "curated_text") -> dict:
    return {
        "query_id": "q1",
        "query": "사업 요약해줘",
        "query_type": query_type,
        "answer": "본 사업은 학사정보시스템 고도화이다.",
        "sources": [{"chunk_id": "doc:000:chunk:0"}],
        "source_texts": ["학사정보시스템 고도화 사업 본문"],
    }


def test_judge_scores_each_prediction() -> None:
    metrics = {"faithfulness": _StubMetric("faithfulness", 0.9), "answer_relevancy": _StubMetric("answer_relevancy", 0.8)}

    judged = judge_predictions([_prediction()], metrics=metrics)

    assert judged[0]["judge"]["faithfulness"] == 0.9
    assert judged[0]["judge"]["answer_relevancy"] == 0.8
    assert judged[0]["judge"]["warnings"] == []


def test_judge_skips_abstention_questions() -> None:
    metrics = {"faithfulness": _StubMetric("faithfulness", 0.9)}

    judged = judge_predictions([_prediction(query_type="abstention")], metrics=metrics)

    assert judged[0]["judge"]["faithfulness"] is None
    assert "judge_skipped_abstention" in judged[0]["judge"]["warnings"]


def test_judge_failure_is_isolated_per_metric() -> None:
    metrics = {
        "faithfulness": _StubMetric("faithfulness", RuntimeError("api down")),
        "answer_relevancy": _StubMetric("answer_relevancy", 0.7),
    }

    judged = judge_predictions([_prediction()], metrics=metrics)

    assert judged[0]["judge"]["faithfulness"] is None
    assert judged[0]["judge"]["answer_relevancy"] == 0.7
    assert any(w.startswith("judge_error:faithfulness") for w in judged[0]["judge"]["warnings"])
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_judge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rfp_rag.judge'`

- [ ] **Step 3: 구현**

`rfp_rag/judge.py` 생성:

```python
from __future__ import annotations

import asyncio
import os
from typing import Any

from .providers import require_openai_key

JUDGED_QUERY_TYPES = {"project_budget", "project_deadline", "issuer_lookup", "project_summary", "curated_text"}


def _build_metrics() -> dict[str, Any]:
    """Real RAGAS metrics. Requires OPENAI_API_KEY."""
    require_openai_key()
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import Faithfulness, ResponseRelevancy

    judge_model = os.environ.get("RFP_JUDGE_MODEL", "gpt-5.4")
    embedding_model = os.environ.get("RFP_EMBEDDING_MODEL", "text-embedding-3-small")
    llm = LangchainLLMWrapper(ChatOpenAI(model=judge_model))
    embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model=embedding_model))
    return {
        "faithfulness": Faithfulness(llm=llm),
        "answer_relevancy": ResponseRelevancy(llm=llm, embeddings=embeddings),
    }


def _sample(prediction: dict[str, Any]):
    from ragas import SingleTurnSample

    return SingleTurnSample(
        user_input=prediction["query"],
        response=prediction["answer"],
        retrieved_contexts=list(prediction.get("source_texts") or []),
    )


async def _score_one(prediction: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    judge: dict[str, Any] = {name: None for name in metrics}
    judge["warnings"] = []
    if prediction.get("query_type") not in JUDGED_QUERY_TYPES:
        judge["warnings"].append("judge_skipped_abstention")
        return judge
    sample = _sample(prediction)
    for name, metric in metrics.items():
        try:
            judge[name] = float(await metric.single_turn_ascore(sample))
        except Exception as exc:  # noqa: BLE001 - judge must not break the eval lane
            judge["warnings"].append(f"judge_error:{name}:{type(exc).__name__}")
    return judge


def judge_predictions(
    predictions: list[dict[str, Any]],
    metrics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Attach a `judge` dict to each prediction. Failures degrade to None scores."""
    metrics = metrics if metrics is not None else _build_metrics()

    async def _run() -> list[dict[str, Any]]:
        return [await _score_one(p, metrics) for p in predictions]

    judges = asyncio.run(_run())
    return [dict(p) | {"judge": j} for p, j in zip(predictions, judges)]
```

참고: `_sample`의 `SingleTurnSample` import가 stub 테스트 경로에서도 실행되므로 ragas 설치가 전제다(Task 1에서 설치됨). abstention 스킵 경로는 `_sample`을 호출하지 않는다.

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_judge.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add rfp_rag/judge.py tests/test_judge.py
git commit -m "feat: add RAGAS judge wrapper with per-metric failure isolation"
```

---

### Task 11: evaluate.py — 레인 분기, RAGAS 통합, rag_quality_complete 게이트

**Files:**
- Modify: `rfp_rag/evaluate.py`
- Test: `tests/test_evaluate_report.py` (업데이트), `tests/test_gates.py` (신규)

- [ ] **Step 1: 게이트 판정 단위 테스트 작성 (신규 파일)**

`tests/test_gates.py` 생성:

```python
from __future__ import annotations

from rfp_rag.evaluate import REAL_QUALITY_THRESHOLDS, RAGAS_THRESHOLDS, decide_gates


def _passing_aggregate() -> dict:
    return {
        "recall@3": 0.9,
        "recall@5": 0.95,
        "mrr": 0.9,
        "citation_presence": 1.0,
        "citation_validity": 0.95,
        "metadata_exact_match": 0.95,
        "abstention_pass": 1.0,
        "faithfulness": 0.85,
        "answer_relevancy": 0.75,
    }


def test_real_lane_passes_when_all_thresholds_met() -> None:
    gates = decide_gates("real_openai", _passing_aggregate(), evaluation_valid=True)

    assert gates["thresholds_applied"] is True
    assert gates["rag_quality_complete"] is True


def test_real_lane_fails_below_any_threshold() -> None:
    aggregate = _passing_aggregate() | {"recall@5": 0.8}

    gates = decide_gates("real_openai", aggregate, evaluation_valid=True)

    assert gates["rag_quality_complete"] is False


def test_real_lane_fails_when_evaluation_invalid() -> None:
    gates = decide_gates("real_openai", _passing_aggregate(), evaluation_valid=False)

    assert gates["rag_quality_complete"] is False


def test_offline_lane_never_claims_quality() -> None:
    gates = decide_gates("offline", _passing_aggregate(), evaluation_valid=True)

    assert gates["thresholds_applied"] is False
    assert gates["rag_quality_complete"] is False
    assert gates["offline_scaffold_complete"] is True


def test_thresholds_cover_ragas_metrics() -> None:
    assert RAGAS_THRESHOLDS == {"faithfulness": 0.80, "answer_relevancy": 0.70}
    assert "recall@5" in REAL_QUALITY_THRESHOLDS
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_gates.py -v`
Expected: FAIL — `ImportError: cannot import name 'RAGAS_THRESHOLDS'`

- [ ] **Step 3: evaluate.py 수정 — 게이트 함수 + 레인 분기**

`rfp_rag/evaluate.py`에 다음을 추가/수정한다.

(a) 상수 추가 (`REAL_QUALITY_THRESHOLDS` 아래):

```python
RAGAS_THRESHOLDS = {
    "faithfulness": 0.80,
    "answer_relevancy": 0.70,
}
MAX_ERROR_RATE = 0.10
```

(b) 게이트 판정 함수 추가:

```python
def decide_gates(lane: str, aggregate: dict[str, Any], evaluation_valid: bool) -> dict[str, Any]:
    offline_scaffold_complete = bool(
        aggregate.get("citation_presence") is not None
        and aggregate.get("citation_presence", 0) >= 0.95
        and aggregate.get("citation_validity") is not None
        and aggregate.get("citation_validity", 0) >= 0.90
        and aggregate.get("abstention_pass") is not None
        and aggregate.get("abstention_pass", 0) >= 0.90
    )
    if lane != "real_openai":
        return {
            "thresholds_applied": False,
            "offline_scaffold_complete": offline_scaffold_complete,
            "rag_quality_complete": False,
        }
    thresholds = REAL_QUALITY_THRESHOLDS | RAGAS_THRESHOLDS
    met = all(
        aggregate.get(metric) is not None and aggregate.get(metric, 0.0) >= minimum
        for metric, minimum in thresholds.items()
    )
    return {
        "thresholds_applied": True,
        "offline_scaffold_complete": offline_scaffold_complete,
        "rag_quality_complete": bool(met and evaluation_valid),
    }
```

(c) `evaluate_index` 수정 — 시그니처와 본문:

- `provider` 검증을 `lane = normalize_lane(provider)`로 교체 (`from .providers import normalize_lane` 추가, 기존 `raise ValueError(...fake_offline only...)` 제거)
- `answer_query` import를 `from .rag_chain import answer_query`로 변경
- 질의 루프를 에러 격리 형태로 교체:

```python
    predictions: list[dict[str, Any]] = []
    error_count = 0
    for record in queries:
        try:
            response = answer_query(index_dir, record["query"], top_k=top_k, min_score=min_score)
        except Exception as exc:  # noqa: BLE001 - isolate per-question API failures
            error_count += 1
            response = {
                "query": record["query"],
                "answer": "",
                "sources": [],
                "warnings": [f"answer_error:{type(exc).__name__}"],
                "confidence": "low",
                "retrieved_doc_ids": [],
                "retrieved_chunk_ids": [],
                "scores": [],
            }
        pass_fail = _score_prediction(record, response, top_k=top_k)
        predictions.append(
            {
                "query_id": record["id"],
                "query": record["query"],
                "query_type": record["query_type"],
                "expected_doc_ids": record.get("expected_doc_ids", []),
                "retrieved_doc_ids": response.get("retrieved_doc_ids", []),
                "retrieved_chunk_ids": response.get("retrieved_chunk_ids", []),
                "answer": response.get("answer", ""),
                "sources": response.get("sources", []),
                "source_texts": response.get("source_texts", []),
                "warnings": response.get("warnings", []),
                "scores": response.get("scores", []),
                "pass_fail": pass_fail,
            }
        )
    error_rate = error_count / len(queries) if queries else 0.0
    evaluation_valid = error_rate <= MAX_ERROR_RATE
```

(d) judge용 근거 텍스트: `rag_chain.answer_with_store`의 sources에는 chunk 본문이 없다. judge가 `retrieved_contexts`로 chunk 본문을 받아야 하므로, `rag_chain.answer_with_store`의 정상 응답 dict에 `"source_texts": [r.text for r in results]` 키를 추가하고, `abstention_response`에는 `"source_texts": []`를 추가한다. (c)의 prediction 조립 코드는 이미 `response.get("source_texts", [])`를 읽는다. `tests/test_rag_chain.py`에 단언 추가: in-domain 테스트에 `assert response["source_texts"]`, abstention 테스트에 `assert response["source_texts"] == []`.

(e) real 레인 judge 실행 (`_aggregate` 호출 직전):

```python
    if lane == "real_openai":
        from .judge import judge_predictions

        predictions = judge_predictions(predictions)
```

(f) aggregate에 judge 평균 추가 — `_aggregate(predictions)` 호출 뒤:

```python
    aggregate = _aggregate(predictions)
    if lane == "real_openai":
        aggregate["faithfulness"] = _mean(p.get("judge", {}).get("faithfulness") for p in predictions)
        aggregate["answer_relevancy"] = _mean(p.get("judge", {}).get("answer_relevancy") for p in predictions)
```

(g) 스코어 분포 기록 (abstention 캘리브레이션 근거):

```python
    def _top_score(p: dict[str, Any]) -> float | None:
        return p["scores"][0] if p.get("scores") else None

    score_distribution = {
        "in_domain_top_scores": sorted(
            (s for s in (_top_score(p) for p in predictions if p["query_type"] != "abstention") if s is not None)
        ),
        "abstention_top_scores": sorted(
            (s for s in (_top_score(p) for p in predictions if p["query_type"] == "abstention") if s is not None)
        ),
    }
```

(h) metrics dict 교체 — 기존 `offline_scaffold_complete`/`rag_quality_complete`/`thresholds_applied` 하드코딩 블록을 게이트 함수 호출로:

```python
    gates = decide_gates(lane, aggregate, evaluation_valid)
    metrics: dict[str, Any] = {
        "provider_lane": lane,
        "top_k": top_k,
        "min_score": min_score,
        "error_rate": error_rate,
        "evaluation_valid": evaluation_valid,
        "score_distribution": score_distribution,
        "query_set_counts": {
            "golden_metadata": len(golden),
            "curated_text": len(curated),
            "abstention": len(abstentions),
            "total": len(queries),
        },
        "aggregate": aggregate,
        "per_type": _by_type(predictions),
        "thresholds": REAL_QUALITY_THRESHOLDS | RAGAS_THRESHOLDS,
        **gates,
        "quality_note": (
            "real_openai lane applies thresholds for rag_quality_complete."
            if lane == "real_openai"
            else "offline lane validates deterministic contract only; it does not claim semantic RAG quality."
        ),
    }
```

(i) `evaluate_index` 시그니처에 `min_score: float = 0.05` 추가, argparse에 `--min-score` 추가, `main()`에서 전달.

- [ ] **Step 4: 기존 evaluate 테스트 업데이트**

`tests/test_evaluate_report.py`를 읽고, provider 인자로 `"fake_offline"`을 쓰는 부분은 그대로 두고(별칭 검증) metrics 단언을 새 키에 맞게 수정한다: `metrics["provider_lane"] == "offline"`, `metrics["evaluation_valid"] is True`, 기존 `offline_scaffold_complete`/`rag_quality_complete` 단언 유지.

- [ ] **Step 5: 전체 테스트 통과 확인**

Run: `python3 -m pytest -q`
Expected: 전체 PASS

- [ ] **Step 6: Commit**

```bash
git add rfp_rag/evaluate.py rfp_rag/rag_chain.py tests/test_gates.py tests/test_evaluate_report.py tests/test_rag_chain.py
git commit -m "feat: lane-aware evaluation with RAGAS judge and rag_quality_complete gate"
```

---

### Task 12: contracts.py + report_check + README + real 스모크 테스트

**Files:**
- Modify: `rfp_rag/contracts.py`
- Modify: `rfp_rag/report_check.py` (마커 검증 추가분만)
- Modify: `README.md`
- Test: `tests/test_real_smoke.py` (신규)

- [ ] **Step 1: contracts.py에 real 계약 추가**

`rfp_rag/contracts.py` 끝에 추가:

```python
REAL_CONTRACT_VERSION = "rfp-rag-real-v1"

REAL_REQUIRED_COMMANDS = [
    "python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index_real --chunk-size 500 --chunk-overlap 80 --embedding-provider openai",
    "python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_real --out artifacts/eval_real --provider real_openai --top-k 5",
]


def real_contract() -> dict[str, Any]:
    return {
        "contract_version": REAL_CONTRACT_VERSION,
        "required_eval_files": REQUIRED_EVAL_FILES,
        "required_commands": REAL_REQUIRED_COMMANDS,
        "threshold_policy": (
            "Thresholds may be recalibrated only before a final run, and any change "
            "must be recorded with rationale in the evaluation report."
        ),
        "quality_semantics": {
            "real_openai": {
                "claims_semantic_quality": True,
                "allowed_completion_claim": "rag_quality_complete",
                "requires": ["thresholds_applied", "evaluation_valid"],
            }
        },
    }
```

`offline_contract()`는 변경하지 않는다.

`rfp_rag/evaluate.py`의 contract 기록을 레인에 따라 분기: `_write_json(out_dir / "contract.json", real_contract() if lane == "real_openai" else offline_contract())` (import 추가: `from .contracts import offline_contract, real_contract`).

- [ ] **Step 2: real 스모크 테스트 작성**

`tests/test_real_smoke.py` 생성:

```python
from __future__ import annotations

import os
from pathlib import Path

import pytest

from rfp_rag.providers import build_embeddings

pytestmark = pytest.mark.real

requires_key = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"
)


@requires_key
def test_openai_embeddings_smoke() -> None:
    emb = build_embeddings("real_openai")

    vector = emb.embed_query("한영대학교 학사정보시스템 고도화 사업")

    assert len(vector) >= 256
    assert any(v != 0.0 for v in vector)


@requires_key
def test_llm_generator_smoke() -> None:
    from rfp_rag.index_store import SearchResult
    from rfp_rag.providers import LLMAnswerGenerator

    result = SearchResult(
        chunk_id="doc:000:chunk:0",
        doc_id="doc:000",
        csv_row_id="000",
        score=0.9,
        text="사업명: 한영대학교 학사정보시스템 고도화\n발주기관: 한영대학\n예산은 1억 5천만원이다.",
        metadata={"project_name": "한영대학교 학사정보시스템 고도화", "issuer": "한영대학"},
    )
    gen = LLMAnswerGenerator()

    answer = gen.generate("이 사업 발주 기관은 어디야?", [result])

    assert "한영대학" in answer
```

- [ ] **Step 3: 키 없이 스킵 확인**

Run: `python3 -m pytest tests/test_real_smoke.py -v`
Expected: 2 SKIPPED (`OPENAI_API_KEY not set`) — 키가 있는 환경이면 2 PASS

Run: `python3 -m pytest -q -m "not real"`
Expected: 전체 PASS (CI 기본 실행 형태)

- [ ] **Step 4: README 업데이트**

`README.md`의 Commands 섹션 아래에 real 레인 섹션 추가:

````markdown
## Real provider quality lane (rfp-rag-real-v1)

Requires `OPENAI_API_KEY`. Models default to `text-embedding-3-small` /
`gpt-5.4-mini` (generation) / `gpt-5.4` (judge); override via
`RFP_EMBEDDING_MODEL`, `RFP_GENERATION_MODEL`, `RFP_JUDGE_MODEL`.

```bash
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files \
  --out artifacts/index_real --chunk-size 500 --chunk-overlap 80 --embedding-provider openai
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_real \
  --out artifacts/eval_real --provider real_openai --top-k 5
```

- `rag_quality_complete` requires every threshold in `artifacts/eval_real/metrics.json`
  (`thresholds`) plus `evaluation_valid` (error rate <= 10%).
- Qdrant runs in embedded local mode: single-process only. Delete
  `artifacts/index_real/qdrant` and rebuild to re-index. Production migration path
  is a Docker Qdrant server with the same client API.
- Offline lane stays credential-free: `python3 -m pytest -m "not real"` must pass
  without `OPENAI_API_KEY`.
- Full real cycle cost estimate: under $5 with default models (judge dominates;
  set `RFP_JUDGE_MODEL=gpt-5.4-mini` to cut cost to roughly $1).
````

기존 "Gate semantics" 섹션의 `fake_offline` 단어와 `does not claim semantic quality` 마커 문구는 그대로 유지한다 (report_check 호환).

- [ ] **Step 5: 전체 회귀 + Commit**

Run: `python3 -m pytest -q -m "not real"`
Expected: 전체 PASS

```bash
git add rfp_rag/contracts.py rfp_rag/evaluate.py README.md tests/test_real_smoke.py
git commit -m "feat: add rfp-rag-real-v1 contract, real smoke tests, README lane docs"
```

---

### Task 13: offline 레인 풀 사이클 재생성 + real 레인 실행 절차 (수동 게이트)

**Files:**
- 산출물: `artifacts/index/`, `artifacts/eval/`, (키 보유 시) `artifacts/index_real/`, `artifacts/eval_real/`

- [ ] **Step 1: offline 아티팩트 재생성**

```bash
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index --chunk-size 500 --chunk-overlap 80 --embedding-provider offline
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index --out artifacts/eval --provider offline --top-k 5
python3 -m rfp_rag.report_check --eval artifacts/eval --readme README.md
```

Expected: report_check 통과, `artifacts/eval/metrics.json`에서 `offline_scaffold_complete: true`, `rag_quality_complete: false`, `provider_lane: "offline"` 확인.

주의: offline 레인의 recall/MRR은 기존 fake lexical 대비 다를 수 있다(exact substring bonus 제거). 게이트는 citation/abstention 기준이므로 영향 없지만, abstention 5건이 모두 통과하는지 확인하고, 실패 시 `score_distribution`을 보고 `--min-score`를 조정한다 (in_domain 최저값과 abstention 최고값 사이).

- [ ] **Step 2: real 레인 인덱싱 (OPENAI_API_KEY 필요)**

```bash
export OPENAI_API_KEY=sk-...   # 또는 기존 쉘 환경 사용
python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index_real --chunk-size 500 --chunk-overlap 80 --embedding-provider openai
```

Expected: `artifacts/index_real/manifest.json`에 `embedding_provider: "real_openai"` (CLI 값 `openai`는 `normalize_lane`을 거쳐 통일 식별자로 기록됨), `embedding_model: "text-embedding-3-small"` 기록. `artifacts/index_real/qdrant/` 디렉터리 생성.

- [ ] **Step 3: real 레인 1차 평가 (캘리브레이션 런)**

```bash
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_real --out artifacts/eval_real --provider real_openai --top-k 5 --min-score 0.0
```

`--min-score 0.0`(게이트 비활성)으로 먼저 돌려 `metrics.json`의 `score_distribution`을 확인한다:
- `abstention_top_scores`의 최댓값과 `in_domain_top_scores`의 최솟값 사이 값을 `min_score`로 선택 (보통 OpenAI cosine에서 0.2~0.4 사이가 나온다)
- abstention 5건의 `abstention_pass`가 LLM 프롬프트 방어만으로 이미 1.0이면 그 분포를 그대로 기록

- [ ] **Step 4: real 레인 최종 평가 (게이트 런)**

```bash
python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_real --out artifacts/eval_real --provider real_openai --top-k 5 --min-score <Step 3에서 결정한 값>
```

Expected: `artifacts/eval_real/metrics.json`에서
- `thresholds_applied: true`, `evaluation_valid: true`
- `aggregate`의 모든 지표와 `thresholds` 비교
- 전부 충족 시 `rag_quality_complete: true`

미충족 지표가 있으면: 수치·실패 사례(`predictions.jsonl`)를 보고서에 기록하고 원인 분석(retrieval 실패 vs generation 실패 vs judge 채점)을 남긴다. **임계값을 낮춰 통과시키지 않는다** — 조정이 필요하면 근거를 `report.md`에 기록한다 (real 계약의 threshold_policy).

- [ ] **Step 5: 결과 커밋**

```bash
git add README.md REPORT.md docs/
git commit -m "docs: record real lane evaluation results and calibrated min_score"
```

(artifacts/는 .gitignore 대상이므로 수치는 REPORT.md에 표로 옮겨 기록한다: aggregate 지표, min_score 캘리브레이션 근거, 비용 실측, fake 레인 대비 비교.)

---

## Self-Review 결과 (작성 시 수행)

- **스펙 커버리지**: 레인 통합(T2-T9), Qdrant 로컬 모드(T4), RAGAS judge(T10-T11), 게이트(T11), 에러 격리·실패율 10%(T11), 캘리브레이션 절차(T13), 계약·README(T12), real 스모크(T12) — 스펙 섹션 3~8 전부 태스크에 매핑됨.
- **타입 일관성**: `SearchResult`는 index_store 정의를 전 태스크가 공유. `normalize_lane`/`build_embeddings`/`build_generator` 시그니처는 T7 정의를 T8/T9/T11이 그대로 사용. `source_texts` 키는 T11(d)에서 rag_chain↔evaluate↔judge 세 곳 동기화 명시.
- **알려진 트레이드오프**: T11(d)처럼 앞 태스크 산출물(rag_chain)을 뒤 태스크가 한 줄 수정하는 지점이 한 곳 있다 — 커밋이 분리되어 있므로 실행자는 T11에서 해당 diff를 함께 적용할 것.
