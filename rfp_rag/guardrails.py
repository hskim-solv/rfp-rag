from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    categories: list[str]
    reasons: list[str]


PROMPT_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "disregard previous instructions",
    "system prompt",
    "developer message",
    "reveal your instructions",
    "이전 지시",
    "시스템 프롬프트",
    "개발자 메시지",
)

SECRET_EXFILTRATION_PATTERNS = (
    "openai_api_key",
    "api key",
    "secret",
    "password",
    ".env",
    "환경변수",
    "비밀키",
    "토큰",
)


def check_question_guardrails(question: str) -> GuardrailResult:
    normalized = question.casefold()
    categories: list[str] = []
    reasons: list[str] = []

    if any(pattern in normalized for pattern in PROMPT_INJECTION_PATTERNS):
        categories.append("prompt_injection")
        reasons.append("question contains instruction-override language")
    if any(pattern in normalized for pattern in SECRET_EXFILTRATION_PATTERNS):
        categories.append("secret_exfiltration")
        reasons.append("question asks for secrets or credential material")

    return GuardrailResult(
        allowed=not categories,
        categories=categories,
        reasons=reasons,
    )
