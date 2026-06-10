from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "rfp-rag-offline-v1"

REQUIRED_COMMANDS = [
    "python3 -m pytest",
    "python3 -m rfp_rag.inspect_corpus --data data/data_list.csv --files data/files --out artifacts/corpus_manifest.json",
    "python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index --chunk-size 500 --chunk-overlap 80 --embedding-provider fake",
    "python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index --out artifacts/eval --provider fake_offline --top-k 5",
    "python3 -m rfp_rag.report_check --eval artifacts/eval --readme README.md",
]

REQUIRED_EVAL_FILES = [
    "golden_metadata.jsonl",
    "curated_text_questions.jsonl",
    "abstention_questions.jsonl",
    "metrics.json",
    "predictions.jsonl",
    "report.md",
    "contract.json",
]

README_MARKERS = [
    CONTRACT_VERSION,
    "does not claim semantic quality",
]


def offline_contract() -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "required_eval_files": REQUIRED_EVAL_FILES,
        "required_commands": REQUIRED_COMMANDS,
        "readme_markers": README_MARKERS,
        "quality_semantics": {
            "fake_offline": {
                "claims_semantic_quality": False,
                "allowed_completion_claim": "offline_scaffold_complete",
                "forbidden_completion_claim": "rag_quality_complete",
            }
        },
    }
