from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_package_manifest_includes_hosted_evidence_script() -> None:
    manifest = json.loads(
        (ROOT / "docs/portfolio/public-package-manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["public_safe"] is True
    assert "scripts/deploy-hf-space.sh" in manifest["publishable_artifacts"]
    assert "scripts/local-hosted-demo-smoke.sh" in manifest["publishable_artifacts"]
    assert "scripts/hosted-evidence.sh" in manifest["publishable_artifacts"]
    assert (ROOT / "scripts/deploy-hf-space.sh").is_file()
    assert (ROOT / "scripts/local-hosted-demo-smoke.sh").is_file()
    assert (ROOT / "scripts/hosted-evidence.sh").is_file()
