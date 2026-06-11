"""Langfuse 트레이싱 옵션 연동 (ADR-0001).

LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY가 환경에 있을 때만 활성화된다.
키가 없으면 config를 그대로 돌려보내 offline lane의 credential-free 불변식을 지킨다.
"""

from __future__ import annotations

import os
import sys
from typing import Any

_REQUIRED_KEYS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")


def tracing_enabled() -> bool:
    return all(os.environ.get(key) for key in _REQUIRED_KEYS)


def tracing_callbacks() -> list[Any]:
    """활성화 시 [CallbackHandler], 아니면 [] — LLM 생성자나 invoke config에 그대로 붙인다."""
    if not tracing_enabled():
        return []
    try:
        from langfuse.langchain import CallbackHandler
    except ImportError:
        print(
            "warning: LANGFUSE_* 키가 설정되어 있지만 langfuse 패키지가 없어 트레이싱을 건너뜁니다"
            " (pip install langfuse)",
            file=sys.stderr,
        )
        return []
    return [CallbackHandler()]


def traced_config(config: dict[str, Any]) -> dict[str, Any]:
    """LangGraph invoke config에 Langfuse CallbackHandler를 붙인 사본을 반환한다."""
    callbacks = tracing_callbacks()
    if not callbacks:
        return config
    traced = dict(config)
    traced["callbacks"] = [*config.get("callbacks", []), *callbacks]
    return traced


def flush_tracing() -> None:
    """버퍼링된 트레이스를 Langfuse로 강제 전송한다.

    SDK는 배치 업로드를 쓰므로 단명 CLI 프로세스는 종료 전에 호출해야 트레이스가 유실되지 않는다.
    """
    if not tracing_enabled():
        return
    try:
        from langfuse import get_client
    except ImportError:
        return
    get_client().flush()
