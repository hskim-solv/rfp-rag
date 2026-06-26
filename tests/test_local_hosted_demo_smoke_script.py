from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_local_hosted_demo_smoke_script_runs_public_demo_profile() -> None:
    script = (ROOT / "scripts/local-hosted-demo-smoke.sh").read_text(encoding="utf-8")

    assert "RFP_RAG_PUBLIC_DEMO_MODE=1" in script
    assert "RFP_RAG_RATE_LIMIT_PER_MINUTE=20" in script
    assert "RFP_RAG_GIT_SHA" in script
    assert "uvicorn rfp_rag.service.app:app" in script
    assert "rfp_rag.hosted_demo_smoke" in script
    assert "--expected-git-sha" in script
    assert "local_hosted_demo_smoke_ok=true" in script
