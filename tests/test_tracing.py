from __future__ import annotations

import pytest

from rfp_rag.tracing import flush_tracing, traced_config, tracing_callbacks

# LANGFUSE_BASE_URL은 선택값 (self-host/리전 지정용) — 활성화 판정은 PUBLIC/SECRET 두 키만 본다
_KEYS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")


def _clear_keys(monkeypatch) -> None:
    for key in _KEYS:
        monkeypatch.delenv(key, raising=False)


def test_traced_config_without_keys_is_passthrough(monkeypatch):
    _clear_keys(monkeypatch)
    config = {"configurable": {"thread_id": "t1"}, "recursion_limit": 25}
    out = traced_config(config)
    assert out == {"configurable": {"thread_id": "t1"}, "recursion_limit": 25}
    assert "callbacks" not in out


def test_traced_config_with_keys_attaches_langfuse_handler(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
    config = {"configurable": {"thread_id": "t1"}}
    out = traced_config(config)
    assert out["configurable"]["thread_id"] == "t1"
    assert len(out["callbacks"]) == 1
    from langfuse.langchain import CallbackHandler

    assert isinstance(out["callbacks"][0], CallbackHandler)
    # 원본 config는 변이되지 않는다
    assert "callbacks" not in config


def test_tracing_callbacks_without_keys_is_empty(monkeypatch):
    _clear_keys(monkeypatch)
    assert tracing_callbacks() == []


def test_tracing_callbacks_with_keys_returns_handler(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
    callbacks = tracing_callbacks()
    from langfuse.langchain import CallbackHandler

    assert len(callbacks) == 1
    assert isinstance(callbacks[0], CallbackHandler)


def test_tracing_callbacks_reuses_cached_handler(monkeypatch):
    # 호출마다 새 핸들러를 만들지 않는다 (eval 루프 50회 호출 대비)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    first = tracing_callbacks()
    second = tracing_callbacks()
    assert first[0] is second[0]


def _boom(*args, **kwargs):
    raise RuntimeError("boom")


def test_evaluate_main_flushes_on_exception(monkeypatch):
    from rfp_rag import evaluate

    calls: list[bool] = []
    monkeypatch.setattr(evaluate, "flush_tracing", lambda: calls.append(True))
    monkeypatch.setattr(evaluate, "evaluate_index", _boom)
    with pytest.raises(RuntimeError):
        evaluate.main(["--data", "d.csv", "--index", "i", "--out", "o"])
    assert calls


def test_run_agent_main_flushes_on_exception(monkeypatch):
    from rfp_rag.agent import run_agent

    calls: list[bool] = []
    monkeypatch.setattr(run_agent, "flush_tracing", lambda: calls.append(True))
    monkeypatch.setattr(run_agent, "build_runtime", _boom)
    with pytest.raises(RuntimeError):
        run_agent.main(
            ["--index", "i", "--data", "d.csv", "--files", "f", "--question", "q"]
        )
    assert calls


def test_evaluate_agent_main_flushes_on_exception(monkeypatch):
    from rfp_rag.agent import evaluate_agent as ea

    calls: list[bool] = []
    monkeypatch.setattr(ea, "flush_tracing", lambda: calls.append(True))
    monkeypatch.setattr(ea, "evaluate_agent", _boom)
    with pytest.raises(RuntimeError):
        ea.main(["--data", "d.csv", "--files", "f", "--index", "i", "--out", "o"])
    assert calls


def test_llm_brains_pass_tracing_callbacks(monkeypatch):
    # real lane Router/Rewriter도 generator/judge처럼 callbacks를 명시 주입해야
    # 결정 단계(route/rewrite)가 트레이스에서 빠지지 않는다 (PR #3 Codex 리뷰)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    captured: list[dict] = []

    class _FakeLLM:
        def __init__(self, **kwargs):
            captured.append(kwargs)

        def with_structured_output(self, schema):
            return self

        def invoke(self, messages):
            raise RuntimeError("stop after construction")

    import langchain_openai

    from rfp_rag.agent.brains import LLMQueryRewriter, LLMRouter

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", _FakeLLM)
    with pytest.raises(RuntimeError):
        LLMRouter().route("예산이 가장 큰 공고는?")
    with pytest.raises(RuntimeError):
        LLMQueryRewriter().rewrite("예산이 가장 큰 공고는?", 1)
    assert len(captured) == 2
    assert all(len(kw.get("callbacks") or []) == 1 for kw in captured)


def test_flush_tracing_without_keys_is_noop(monkeypatch):
    _clear_keys(monkeypatch)
    flush_tracing()  # 예외 없이 조용히 반환해야 한다


def test_flush_tracing_with_keys_flushes_client(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")

    class _Recorder:
        flushed = False

        def flush(self):
            _Recorder.flushed = True

    import langfuse

    monkeypatch.setattr(langfuse, "get_client", lambda: _Recorder())
    flush_tracing()
    assert _Recorder.flushed
