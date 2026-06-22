from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rfp_rag.hosted_demo_smoke import HttpResult, run_hosted_demo_smoke


def test_hosted_demo_smoke_verifies_public_safe_reviewer_contract(
    tmp_path: Path,
) -> None:
    seen: list[dict[str, Any]] = []

    def fake_transport(
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_payload: dict[str, Any] | None = None,
    ) -> HttpResult:
        seen.append(
            {
                "method": method,
                "url": url,
                "headers": headers or {},
                "json_payload": json_payload,
            }
        )
        if url.endswith("/healthz"):
            return HttpResult(
                200, {"ok": True, "service": "rfp-rag", "git_sha": "abc1234"}, ""
            )
        if url.endswith("/v1/gates"):
            return HttpResult(
                200,
                {
                    "overall_ok": True,
                    "public_demo_gate": True,
                    "lanes": {"hosted_reviewer_demo": {"ok": True}},
                },
                "",
            )
        if url.endswith("/v1/answer/stream"):
            body = (
                'event: status\ndata: {"status":"started"}\n\n'
                'event: final\ndata: {"metadata":{"provider":"public_demo"}}\n\n'
            )
            return HttpResult(200, None, body)
        if url.endswith("/v1/answer") and not headers:
            return HttpResult(401, {"detail": {"code": "reviewer_token_required"}}, "")
        if url.endswith("/v1/answer"):
            return HttpResult(
                200,
                {
                    "answer": "public-safe",
                    "metadata": {"provider": "public_demo"},
                    "sources": [{"filename": "public-safe-demo.md"}],
                },
                "",
            )
        raise AssertionError(url)

    out = tmp_path / "artifacts/hosted_demo_smoke/summary.json"
    summary = run_hosted_demo_smoke(
        base_url="https://example.invalid",
        reviewer_token="review-token",
        expected_git_sha="abc1234",
        out=out,
        transport=fake_transport,
    )

    assert summary["hosted_demo_smoke_complete"] is True
    assert summary["metrics"] == {
        "healthz_pass": 1.0,
        "reviewer_token_boundary_pass": 1.0,
        "gates_pass": 1.0,
        "answer_pass": 1.0,
        "stream_pass": 1.0,
        "public_safe_sources_pass": 1.0,
        "expected_git_sha_present": 1.0,
        "revision_match_pass": 1.0,
    }
    assert summary["failed"] == []
    assert json.loads(out.read_text(encoding="utf-8")) == summary
    protected_calls = [
        item
        for item in seen
        if item["url"].endswith(("/v1/gates", "/v1/answer", "/v1/answer/stream"))
        and item["headers"]
    ]
    assert all(
        item["headers"].get("X-Reviewer-Token") == "review-token"
        for item in protected_calls
    )


def test_hosted_demo_smoke_fails_closed_on_revision_mismatch(
    tmp_path: Path,
) -> None:
    def fake_transport(
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_payload: dict[str, Any] | None = None,
    ) -> HttpResult:
        if url.endswith("/healthz"):
            return HttpResult(
                200, {"ok": True, "service": "rfp-rag", "git_sha": "old1234"}, ""
            )
        if url.endswith("/v1/gates"):
            return HttpResult(200, {"overall_ok": True, "public_demo_gate": True}, "")
        if url.endswith("/v1/answer/stream"):
            return HttpResult(200, None, "event: final\ndata: {}\n\n")
        if url.endswith("/v1/answer") and not headers:
            return HttpResult(401, {"detail": {"code": "reviewer_token_required"}}, "")
        if url.endswith("/v1/answer"):
            return HttpResult(
                200,
                {
                    "answer": "public-safe",
                    "metadata": {"provider": "public_demo"},
                    "sources": [{"filename": "public-safe-demo.md"}],
                },
                "",
            )
        raise AssertionError(url)

    summary = run_hosted_demo_smoke(
        base_url="https://example.invalid",
        reviewer_token="review-token",
        expected_git_sha="new1234",
        out=tmp_path / "summary.json",
        transport=fake_transport,
    )

    assert summary["hosted_demo_smoke_complete"] is False
    assert "revision_match_pass" in summary["failed"]


def test_hosted_demo_smoke_requires_public_demo_gate(tmp_path: Path) -> None:
    def fake_transport(
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_payload: dict[str, Any] | None = None,
    ) -> HttpResult:
        if url.endswith("/healthz"):
            return HttpResult(
                200, {"ok": True, "service": "rfp-rag", "git_sha": "abc1234"}, ""
            )
        if url.endswith("/v1/gates"):
            return HttpResult(200, {"overall_ok": True, "lanes": {}}, "")
        if url.endswith("/v1/answer/stream"):
            return HttpResult(200, None, "event: final\ndata: {}\n\n")
        if url.endswith("/v1/answer") and not headers:
            return HttpResult(401, {"detail": {"code": "reviewer_token_required"}}, "")
        if url.endswith("/v1/answer"):
            return HttpResult(
                200,
                {
                    "answer": "public-safe",
                    "metadata": {"provider": "public_demo"},
                    "sources": [{"filename": "public-safe-demo.md"}],
                },
                "",
            )
        raise AssertionError(url)

    summary = run_hosted_demo_smoke(
        base_url="https://example.invalid",
        reviewer_token="review-token",
        expected_git_sha="abc1234",
        out=tmp_path / "summary.json",
        transport=fake_transport,
    )

    assert summary["hosted_demo_smoke_complete"] is False
    assert "gates_pass" in summary["failed"]


def test_hosted_demo_smoke_fails_closed_on_non_demo_answer(tmp_path: Path) -> None:
    def fake_transport(
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_payload: dict[str, Any] | None = None,
    ) -> HttpResult:
        if url.endswith("/healthz"):
            return HttpResult(200, {"ok": True}, "")
        if url.endswith("/v1/gates"):
            return HttpResult(200, {"overall_ok": True, "public_demo_gate": True}, "")
        if url.endswith("/v1/answer/stream"):
            return HttpResult(200, None, "event: final\ndata: {}\n\n")
        if url.endswith("/v1/answer") and not headers:
            return HttpResult(401, {"detail": {"code": "reviewer_token_required"}}, "")
        if url.endswith("/v1/answer"):
            return HttpResult(
                200,
                {"metadata": {"provider": "offline"}, "sources": []},
                "",
            )
        raise AssertionError(url)

    summary = run_hosted_demo_smoke(
        base_url="https://example.invalid",
        reviewer_token="review-token",
        out=tmp_path / "summary.json",
        transport=fake_transport,
    )

    assert summary["hosted_demo_smoke_complete"] is False
    assert "answer_pass" in summary["failed"]
    assert "public_safe_sources_pass" in summary["failed"]
