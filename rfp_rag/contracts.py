from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "rfp-rag-offline-v1"

# --min-score 0.15 is the calibrated offline cutoff (rationale: score_distribution in metrics.json).
REQUIRED_COMMANDS = [
    "python3 -m pytest",
    "python3 -m rfp_rag.inspect_corpus --data data/data_list.csv --files data/files --out artifacts/corpus_manifest.json",
    "python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index --chunk-size 500 --chunk-overlap 80 --embedding-provider offline",
    "python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index --out artifacts/eval --provider offline --top-k 5 --min-score 0.15",
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
        "required_eval_files": list(REQUIRED_EVAL_FILES),
        "required_commands": REQUIRED_COMMANDS,
        "readme_markers": README_MARKERS,
        "quality_semantics": {
            "offline": {
                "claims_semantic_quality": False,
                "allowed_completion_claim": "offline_scaffold_complete",
                "forbidden_completion_claim": "rag_quality_complete",
            }
        },
    }


REAL_CONTRACT_VERSION = "rfp-rag-real-v1"

REAL_REQUIRED_COMMANDS = [
    "python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index_real --chunk-size 500 --chunk-overlap 80 --embedding-provider openai",
    "python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_real --out artifacts/eval_real --provider real_openai --top-k 5 --min-score 0.47",
]


def real_contract() -> dict[str, Any]:
    return {
        "contract_version": REAL_CONTRACT_VERSION,
        "required_eval_files": list(REQUIRED_EVAL_FILES),
        "required_commands": REAL_REQUIRED_COMMANDS,
        "threshold_policy": (
            "Thresholds may be recalibrated only before a final run, and any change "
            "must be recorded with rationale in the evaluation report."
        ),
        "quality_semantics": {
            "real_openai": {
                "claims_semantic_quality": True,
                "allowed_completion_claim": "rag_quality_complete",
                # rag_quality_complete in metrics.json is the authoritative gate computed by decide_gates.
                "requires": ["thresholds_met", "evaluation_valid"],
            }
        },
    }
