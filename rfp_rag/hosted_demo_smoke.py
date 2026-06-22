from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_QUESTION = "공개 데모에서 검증 가능한 기능과 한계를 알려줘"


@dataclass(frozen=True)
class HttpResult:
    status_code: int
    json_body: dict[str, Any] | None
    text: str


Transport = Callable[..., HttpResult]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _json_or_none(text: str) -> dict[str, Any] | None:
    if not text.strip():
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def urllib_transport(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_payload: dict[str, Any] | None = None,
) -> HttpResult:
    body = None
    request_headers = dict(headers or {})
    if json_payload is not None:
        body = json.dumps(json_payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:  # noqa: S310
            text = response.read().decode("utf-8", errors="replace")
            return HttpResult(response.status, _json_or_none(text), text)
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return HttpResult(exc.code, _json_or_none(text), text)


def _metric(ok: bool) -> float:
    return 1.0 if ok else 0.0


def _auth_headers(reviewer_token: str | None) -> dict[str, str]:
    return {"X-Reviewer-Token": reviewer_token} if reviewer_token else {}


def _public_safe_sources_pass(answer_body: dict[str, Any] | None) -> bool:
    if not answer_body:
        return False
    sources = answer_body.get("sources")
    if not isinstance(sources, list) or not sources:
        return False
    text = json.dumps(answer_body, ensure_ascii=False)
    return (
        "public-safe-demo.md" in text
        and "OPENAI_API_KEY" not in text
        and "원본 RFP 본문" not in text
    )


def run_hosted_demo_smoke(
    *,
    base_url: str,
    reviewer_token: str | None = None,
    out: Path = Path("artifacts/hosted_demo_smoke/summary.json"),
    question: str = DEFAULT_QUESTION,
    transport: Transport = urllib_transport,
) -> dict[str, Any]:
    protected_headers = _auth_headers(reviewer_token)
    answer_payload = {"question": question, "index_dir": "artifacts/index"}

    health = transport("GET", _url(base_url, "/healthz"))
    unauth_answer = (
        transport("POST", _url(base_url, "/v1/answer"), json_payload=answer_payload)
        if reviewer_token
        else HttpResult(401, {"detail": {"code": "reviewer_token_not_configured"}}, "")
    )
    gates = transport("GET", _url(base_url, "/v1/gates"), headers=protected_headers)
    answer = transport(
        "POST",
        _url(base_url, "/v1/answer"),
        headers=protected_headers,
        json_payload=answer_payload,
    )
    stream = transport(
        "POST",
        _url(base_url, "/v1/answer/stream"),
        headers=protected_headers,
        json_payload=answer_payload,
    )

    answer_body = answer.json_body or {}
    metrics = {
        "healthz_pass": _metric(
            health.status_code == 200 and (health.json_body or {}).get("ok") is True
        ),
        "reviewer_token_boundary_pass": _metric(
            reviewer_token is not None
            and unauth_answer.status_code == 401
            and ((unauth_answer.json_body or {}).get("detail") or {}).get("code")
            == "reviewer_token_required"
        ),
        "gates_pass": _metric(gates.status_code == 200 and gates.json_body is not None),
        "answer_pass": _metric(
            answer.status_code == 200
            and (answer_body.get("metadata") or {}).get("provider") == "public_demo"
        ),
        "stream_pass": _metric(
            stream.status_code == 200 and "event: final" in stream.text
        ),
        "public_safe_sources_pass": _metric(_public_safe_sources_pass(answer_body)),
    }
    thresholds = {key: 1.0 for key in metrics}
    failed = [key for key, threshold in thresholds.items() if metrics[key] != threshold]
    summary = {
        "hosted_demo_smoke_complete": not failed,
        "base_url": base_url.rstrip("/"),
        "reviewer_token_boundary": "required" if reviewer_token else "missing",
        "question": question,
        "metrics": metrics,
        "thresholds": thresholds,
        "failed": failed,
        "observed_status": {
            "healthz": health.status_code,
            "unauth_answer": unauth_answer.status_code,
            "gates": gates.status_code,
            "answer": answer.status_code,
            "stream": stream.status_code,
        },
    }
    _write_json(out, summary)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smoke-test a public-safe hosted RFP reviewer demo URL."
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--reviewer-token")
    parser.add_argument(
        "--out", type=Path, default=Path("artifacts/hosted_demo_smoke/summary.json")
    )
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    summary = run_hosted_demo_smoke(
        base_url=args.base_url,
        reviewer_token=args.reviewer_token,
        out=args.out,
        question=args.question,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["hosted_demo_smoke_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
