from __future__ import annotations

from rfp_rag.agent.evaluate_agent import AGENT_THRESHOLDS, decide_agent_gate
from rfp_rag.contracts import agent_contract


def _passing_metrics() -> dict:
    return {
        "routing_accuracy": 0.95,
        "tool_accuracy": 0.90,
        "rewrite_recovery": 0.60,
        "loop_termination": 1.0,
        "abstention_accuracy": 1.0,
        "citation_presence": 1.0,
        "citation_validity": 1.0,
        "metadata_exact_match": 0.95,
    }


def test_gate_passes_at_thresholds() -> None:
    gate = decide_agent_gate(_passing_metrics(), evaluation_valid=True)
    assert gate["agent_lane_complete"] is True
    assert gate["thresholds_applied"] is True
    assert gate["failed"] == []


def test_gate_fails_below_any_threshold() -> None:
    metrics = _passing_metrics()
    metrics["routing_accuracy"] = 0.89
    gate = decide_agent_gate(metrics, evaluation_valid=True)
    assert gate["agent_lane_complete"] is False
    assert "routing_accuracy" in gate["failed"]


def test_gate_fails_on_invalid_evaluation_or_missing_metric() -> None:
    gate = decide_agent_gate(_passing_metrics(), evaluation_valid=False)
    assert gate["agent_lane_complete"] is False
    metrics = _passing_metrics()
    metrics["tool_accuracy"] = None
    gate2 = decide_agent_gate(metrics, evaluation_valid=True)
    assert gate2["agent_lane_complete"] is False
    assert "tool_accuracy" in gate2["failed"]


def test_thresholds_match_design() -> None:
    assert AGENT_THRESHOLDS["routing_accuracy"] == 0.90
    assert AGENT_THRESHOLDS["rewrite_recovery"] == 0.60
    assert AGENT_THRESHOLDS["loop_termination"] == 1.0


def test_agent_contract_shape() -> None:
    c = agent_contract()
    assert c["contract_version"] == "rfp-agent-v1"
    assert any("evaluate_agent" in cmd for cmd in c["required_commands"])
    semantics = c["quality_semantics"]["agent_offline"]
    assert semantics["allowed_completion_claim"] == "agent_lane_complete"
