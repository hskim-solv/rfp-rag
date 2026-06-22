from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_render_blueprint_defines_public_safe_free_web_service() -> None:
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))

    service = blueprint["services"][0]
    assert service["type"] == "web"
    assert service["name"] == "rfp-rag-reviewer-demo"
    assert service["runtime"] == "docker"
    assert service["dockerfilePath"] == "./Dockerfile"
    assert service["plan"] == "free"
    assert service["healthCheckPath"] == "/healthz"

    env = {item["key"]: item for item in service["envVars"]}
    assert env["RFP_RAG_PUBLIC_DEMO_MODE"]["value"] == "1"
    assert env["RFP_RAG_RATE_LIMIT_PER_MINUTE"]["value"] == "20"
    assert env["RFP_RAG_GIT_SHA"]["sync"] is False
    assert env["RFP_RAG_REVIEWER_TOKEN"]["sync"] is False


def test_dockerfile_uses_render_port_with_local_default() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "${PORT:-8000}" in dockerfile
    assert "os.getenv('PORT', '8000')" in dockerfile
