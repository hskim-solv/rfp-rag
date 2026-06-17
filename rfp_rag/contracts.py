from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "rfp-rag-offline-v4"

# --min-score 0.34 is the calibrated section-aware source-first offline cutoff
# (rationale: score_distribution in metrics.json).
REQUIRED_COMMANDS = [
    "python3 -m pytest",
    "python3 -m rfp_rag.inspect_corpus --data data/data_list.csv --files data/files --out artifacts/corpus_manifest.json",
    "python3 -m rfp_rag.parse_sources --data data/data_list.csv --files data/files --out artifacts/parsed_docs",
    "python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index --chunk-size 500 --chunk-overlap 80 --embedding-provider offline --parse-manifest artifacts/parsed_docs/manifest.jsonl",
    "python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index --out artifacts/eval --provider offline --top-k 5 --min-score 0.34 --visual-records artifacts/visual_structure_reviewed/records.jsonl",
    "python3 -m rfp_rag.report_check --eval artifacts/eval --readme README.md",
]

REQUIRED_EVAL_FILES = [
    "golden_metadata.jsonl",
    "curated_text_questions.jsonl",
    "section_lookup_questions.jsonl",
    "cross_document_questions.jsonl",
    "visual_table_questions.jsonl",
    "paraphrase_questions.jsonl",
    "abstention_questions.jsonl",
    "eval_progress.jsonl",
    "metrics.json",
    "predictions.jsonl",
    "predictions_unjudged.jsonl",
    "predictions_unjudged_partial.jsonl",
    "predictions_judged_partial.jsonl",
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


REAL_CONTRACT_VERSION = "rfp-rag-real-v5"

REAL_REQUIRED_COMMANDS = [
    "python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index_real --chunk-size 500 --chunk-overlap 80 --embedding-provider openai --parse-manifest artifacts/parsed_docs/manifest.jsonl",
    "python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_real --out artifacts/eval_real --provider real_openai --top-k 5 --min-score 0.47 --visual-records artifacts/visual_structure_reviewed/records.jsonl",
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


OPEN_CONTRACT_VERSION = "rfp-rag-open-v4"

OPEN_REQUIRED_COMMANDS = [
    "python3 -m rfp_rag.build_index --data data/data_list.csv --files data/files --out artifacts/index_open --chunk-size 500 --chunk-overlap 80 --embedding-provider open --parse-manifest artifacts/parsed_docs/manifest.jsonl",
    "python3 -m rfp_rag.evaluate --data data/data_list.csv --index artifacts/index_open --out artifacts/eval_open --provider open --top-k 5 --min-score 0.55 --visual-records artifacts/visual_structure_reviewed/records.jsonl",
]


def open_contract() -> dict[str, Any]:
    return {
        "contract_version": OPEN_CONTRACT_VERSION,
        "required_eval_files": list(REQUIRED_EVAL_FILES),
        "required_commands": OPEN_REQUIRED_COMMANDS,
        "quality_semantics": {
            "open": {
                # open lane은 저비용 이터레이션 신호 전용 — 게이트 증거가 아니다.
                # 최종 게이트(rag_quality_complete)는 real_openai lane에서만 판정한다.
                "claims_semantic_quality": False,
                "allowed_completion_claim": None,
                "forbidden_completion_claim": "rag_quality_complete",
            }
        },
    }


AGENT_CONTRACT_VERSION = "rfp-agent-v1"

AGENT_REQUIRED_COMMANDS = [
    "python3 -m pytest",
    "python3 -m rfp_rag.agent.evaluate_agent --data data/data_list.csv --files data/files --index artifacts/index --out artifacts/eval_agent --provider offline --top-k 5 --min-score 0.34",
]

AGENT_REQUIRED_EVAL_FILES = [
    "scenarios.jsonl",
    "predictions.jsonl",
    "metrics.json",
    "report.md",
    "contract.json",
]


def agent_contract() -> dict[str, Any]:
    return {
        "contract_version": AGENT_CONTRACT_VERSION,
        "required_eval_files": list(AGENT_REQUIRED_EVAL_FILES),
        "required_commands": AGENT_REQUIRED_COMMANDS,
        "gate_semantics": (
            "agent_lane_complete is decided on the offline lane: graph topology, tools, "
            "HITL and loop termination are deterministic. Real-lane router/rewriter quality "
            "is covered by @pytest.mark.real smoke plus a small real evaluation recorded in REPORT.md."
        ),
        "quality_semantics": {
            "agent_offline": {
                "claims_semantic_quality": False,
                "allowed_completion_claim": "agent_lane_complete",
                "requires": ["thresholds_met", "evaluation_valid"],
            }
        },
    }
