from __future__ import annotations

import hashlib
import math
import os
from typing import Callable, Protocol
from urllib.parse import urlparse

from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, Field

from .fake_provider import lexical_features
from .index_store import SearchResult
from .tracing import tracing_callbacks


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
            # signed hashing trick: collisions cancel in expectation
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


class AnswerGenerator(Protocol):
    """Generates the answer string for a query given retrieved chunks.

    Contract: ``results`` MUST be non-empty. Callers gate empty/low-score
    retrieval before calling (see ``rag_chain.answer_with_store``).
    """

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


SYSTEM_PROMPT = (
    "당신은 B2G 입찰지원 컨설팅 '입찰메이트'의 RFP 분석 어시스턴트입니다. "
    "반드시 아래 제공된 근거 chunk 내용만 사용해 한국어로 답하세요. "
    "모든 답변은 근거가 된 chunk id를 cited_chunk_ids에 담으세요. "
    "근거가 부족하면 insufficient_context를 true로 하고 answer에 '없는 정보'를 포함하세요. "
    "금액·날짜·기관명은 근거 원문 표기 그대로 인용하세요. "
    "각 chunk의 사업금액·입찰마감·발주기관·공고요약은 공고 등록 정보(메타데이터)로서 "
    "금액·날짜·기관명·요약 질문의 공식 출처이며, 본문 표기와 다를 경우 "
    "공고 등록 정보를 우선해 그대로 인용하세요. "
    "금액·날짜·기관명 질문에는 값만 답하지 말고, 질문에 나온 사업명과 묻는 항목을 "
    "문장 안에 그대로 되짚는 완결된 한 문장으로 답하세요. "
    "예: '<사업명>의 입찰 참여 마감일은 2024-10-15T17:00:00입니다.', "
    "'<사업명>의 발주 기관은 <기관명>입니다.', '<사업명>의 사업 금액은 130,000,000원입니다.' "
    "이때 값(ISO 날짜·숫자·기관명)은 공고 등록 정보 표기를 그대로 유지하세요. "
    "요약을 요청받으면 첫 줄에 '<사업명> 요약:'을 적고, 바로 다음 줄부터 해당 chunk의 "
    "공고요약 블록 전체를 옮겨 적으세요. 공고요약은 보통 '- '로 시작하는 여러 줄 목록이며, "
    "줄바꿈과 '- ' 기호를 포함해 한 글자도 바꾸거나 줄이거나 다듬지 말고 그대로 복사하고, "
    "블록 뒤에 어떤 문장도 덧붙이지 마세요."
)


class LLMAnswer(BaseModel):
    answer: str = Field(description="근거 기반 한국어 답변")
    cited_chunk_ids: list[str] = Field(
        default_factory=list, description="답변 근거 chunk id 목록"
    )
    insufficient_context: bool = Field(default=False, description="근거 부족 여부")


def chunk_context_block(result: SearchResult) -> str:
    """Render one retrieved chunk as the context block shown to the LLM and the judge.

    Includes the registry metadata (공고 등록 정보) because golden answers come from
    CSV metadata that the document body may lack or contradict.
    """
    md = result.metadata
    lines = [f"[{result.chunk_id}] 사업명: {md.get('project_name', '')}"]
    if md.get("issuer"):
        lines.append(f"발주기관: {md['issuer']}")
    if md.get("budget_krw_int") is not None:
        lines.append(f"사업금액: {md['budget_krw_int']:,}원")
    deadline = md.get("bid_end_at_iso") or md.get("bid_end_at_raw")
    if deadline:
        lines.append(f"입찰마감: {deadline}")
    summary = (md.get("summary") or "").strip()
    if summary:
        lines.append(f"공고요약: {summary}")
    section_path = md.get("section_path") or []
    if section_path:
        lines.append(f"섹션: {' > '.join(str(part) for part in section_path)}")
    elif md.get("section_title"):
        lines.append(f"섹션: {md['section_title']}")
    if md.get("section_page_start") is not None:
        page = str(md["section_page_start"])
        if md.get("section_page_end") not in (None, md.get("section_page_start")):
            page = f"{page}-{md['section_page_end']}"
        lines.append(f"페이지: {page}")
    visual_evidence = md.get("visual_evidence") or []
    if visual_evidence:
        lines.append("시각근거:")
        for evidence in visual_evidence:
            doc_id = evidence.get("doc_id") or result.doc_id
            page = evidence.get("page")
            page_label = f"p{page}" if page is not None else "p?"
            visual_type = evidence.get("visual_type") or "visual"
            value = evidence.get("value") or ""
            lines.append(f"- {doc_id} {page_label} {visual_type}: {value}")
    lines.append(f"본문: {result.text}")
    return "\n".join(lines)


def build_answer_prompt(query: str, results: list[SearchResult]) -> str:
    context = "\n\n".join(chunk_context_block(r) for r in results)
    return f"근거 chunk 목록:\n\n{context}\n\n질문: {query}"


def _default_invoke(prompt: str) -> LLMAnswer:
    from langchain_openai import ChatOpenAI

    model = os.environ.get("RFP_GENERATION_MODEL", "gpt-5.4-mini")
    llm = ChatOpenAI(model=model, callbacks=tracing_callbacks()).with_structured_output(
        LLMAnswer
    )
    return llm.invoke([("system", SYSTEM_PROMPT), ("human", prompt)])


def _open_invoke(prompt: str) -> LLMAnswer:
    import langchain_openai

    base_url = os.environ.get("RFP_OPEN_BASE_URL", DEFAULT_OPEN_BASE_URL)
    llm = langchain_openai.ChatOpenAI(
        model=os.environ.get("RFP_OPEN_MODEL", DEFAULT_OPEN_MODEL),
        base_url=base_url,
        api_key=_open_api_key(base_url),
        callbacks=tracing_callbacks(),
        # DeepSeek v4는 thinking이 기본인데 thinking 모드는 tool_choice 강제와
        # 충돌한다 (400 "Thinking mode does not support this tool_choice").
        # 미지원 백엔드(Ollama 등)는 이 필드를 무시한다.
        extra_body={"thinking": {"type": "disabled"}},
        # OpenAI 호환 백엔드(DeepSeek 등)는 response_format=json_schema를 지원하지
        # 않는 경우가 많다 — tool call 기반 구조화 출력을 강제한다
    ).with_structured_output(LLMAnswer, method="function_calling")
    return llm.invoke([("system", SYSTEM_PROMPT), ("human", prompt)])


class LLMAnswerGenerator:
    """Real lane generator: ChatOpenAI structured output with citation validation."""

    def __init__(self, invoke: Callable[[str], LLMAnswer] | None = None) -> None:
        self._invoke = invoke or _default_invoke
        self.last_cited_chunk_ids: list[str] = []

    def generate(self, query: str, results: list[SearchResult]) -> str:
        payload = self._invoke(build_answer_prompt(query, results))
        retrieved_ids = {r.chunk_id for r in results}
        self.last_cited_chunk_ids = [
            cid for cid in payload.cited_chunk_ids if cid in retrieved_ids
        ]
        if payload.insufficient_context:
            answer = payload.answer or ""
            return answer if "없는 정보" in answer else f"{answer} 없는 정보".strip()
        return payload.answer


LANE_OFFLINE = "offline"
LANE_REAL_OPENAI = "real_openai"
LANE_OPEN = "open"

_LANE_ALIASES = {
    "offline": LANE_OFFLINE,
    "fake": LANE_OFFLINE,
    "fake_offline": LANE_OFFLINE,
    "openai": LANE_REAL_OPENAI,
    "real_openai": LANE_REAL_OPENAI,
    "open": LANE_OPEN,
}

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

# open lane: OpenAI 호환 base_url 오버라이드 — 생성은 DeepSeek 기본, 임베딩은 로컬
# Ollama(bge-m3) 기본. base_url만 바꾸면 Ollama/OpenRouter 등으로 교체 가능 (ADR-0005).
DEFAULT_OPEN_BASE_URL = "https://api.deepseek.com"
DEFAULT_OPEN_MODEL = "deepseek-v4-flash"
DEFAULT_OPEN_EMBEDDING_BASE_URL = "http://localhost:11434/v1"
DEFAULT_OPEN_EMBEDDING_MODEL = "bge-m3"


def normalize_lane(value: str) -> str:
    lane = _LANE_ALIASES.get((value or "").strip().lower())
    if lane is None:
        raise ValueError(
            f"unknown lane: {value!r} (expected one of {sorted(_LANE_ALIASES)})"
        )
    return lane


def require_openai_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY required for real lane (offline lane runs without credentials)"
        )


def _is_local_url(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host in ("localhost", "127.0.0.1", "::1")


def _open_api_key(base_url: str) -> str:
    key = os.environ.get("RFP_OPEN_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    if _is_local_url(base_url):
        return (
            "ollama"  # 로컬 서버는 키를 검사하지 않지만 클라이언트가 빈 값을 거부한다
        )
    raise RuntimeError(
        "RFP_OPEN_API_KEY or DEEPSEEK_API_KEY required for the open lane remote "
        f"backend ({base_url}); local backends (e.g. Ollama) run without credentials"
    )


def embedding_model_name(lane: str) -> str:
    lane = normalize_lane(lane)
    if lane == LANE_OFFLINE:
        return "lexical-hash-v1"
    if lane == LANE_OPEN:
        return os.environ.get("RFP_OPEN_EMBEDDING_MODEL", DEFAULT_OPEN_EMBEDDING_MODEL)
    return os.environ.get("RFP_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def build_embeddings(lane: str) -> Embeddings:
    lane = normalize_lane(lane)
    if lane == LANE_OFFLINE:
        return LexicalHashEmbeddings()
    from langchain_openai import OpenAIEmbeddings

    if lane == LANE_OPEN:
        base_url = os.environ.get(
            "RFP_OPEN_EMBEDDING_BASE_URL", DEFAULT_OPEN_EMBEDDING_BASE_URL
        )
        return OpenAIEmbeddings(
            model=embedding_model_name(lane),
            base_url=base_url,
            api_key=_open_api_key(base_url),
            # 비OpenAI 서버는 tiktoken 토큰 배열 입력을 디코드하지 못한다 — 문자열로 전송
            check_embedding_ctx_length=False,
        )
    require_openai_key()
    return OpenAIEmbeddings(model=embedding_model_name(lane))


def build_generator(lane: str) -> AnswerGenerator:
    lane = normalize_lane(lane)
    if lane == LANE_OFFLINE:
        return TemplateAnswerGenerator()
    if lane == LANE_OPEN:
        # fail fast: 평가 루프에 들어가기 전에 자격증명 부재를 드러낸다
        _open_api_key(os.environ.get("RFP_OPEN_BASE_URL", DEFAULT_OPEN_BASE_URL))
        return LLMAnswerGenerator(invoke=_open_invoke)
    require_openai_key()
    return LLMAnswerGenerator()
