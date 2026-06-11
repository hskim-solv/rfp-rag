from __future__ import annotations

from rfp_rag.tracing import flush_tracing, traced_config, tracing_callbacks

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
