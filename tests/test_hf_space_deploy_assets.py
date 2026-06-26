from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hf_space_docker_assets_define_public_safe_service() -> None:
    readme = (ROOT / "deploy/hf-space/README.md").read_text(encoding="utf-8")
    dockerfile = (ROOT / "deploy/hf-space/Dockerfile").read_text(encoding="utf-8")

    assert "sdk: docker" in readme
    assert "app_port: 7860" in readme
    assert "uvicorn rfp_rag.service.app:app" in dockerfile
    assert "${PORT:-7860}" in dockerfile
    assert "/healthz" in dockerfile


def test_hf_space_deploy_script_sets_variables_and_secret_without_echoing_token() -> (
    None
):
    script = (ROOT / "scripts/deploy-hf-space.sh").read_text(encoding="utf-8")

    assert "HF_SPACE_ID" in script
    assert "hskim-solv/rfp-rag-reviewer-demo" in script
    assert "RFP_RAG_PUBLIC_DEMO_MODE" in script
    assert "RFP_RAG_RATE_LIMIT_PER_MINUTE" in script
    assert "RFP_RAG_GIT_SHA" in script
    assert "add_space_secret" in script
    assert "RFP_RAG_REVIEWER_TOKEN" in script
    assert 'echo "$RFP_RAG_REVIEWER_TOKEN"' not in script
