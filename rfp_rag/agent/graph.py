from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from .nodes import AgentRuntime
from .state import AgentState

RECURSION_LIMIT = 25


def initial_state(question: str) -> AgentState:
    return {"question": question, "rewrite_count": 0, "tool_calls": []}


def run_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}


def sqlite_checkpointer(path: Path) -> BaseCheckpointSaver:
    from langgraph.checkpoint.sqlite import SqliteSaver

    path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(str(path), check_same_thread=False))


def build_agent_graph(runtime: AgentRuntime, checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(AgentState)
    g.add_node("route", runtime.route_node)
    g.add_node("retrieve", runtime.retrieve_node)
    g.add_node("grade", runtime.grade_node)
    g.add_node("rewrite", runtime.rewrite_node)
    g.add_node("tool_exec", runtime.tool_exec_node)
    g.add_node("generate", runtime.generate_node)
    g.add_node("regenerate", runtime.regenerate_node)
    g.add_node("verify", runtime.verify_node)
    g.add_node("abstain", runtime.abstain_node)
    g.add_node("save_report", runtime.save_report_node)
    g.add_node("respond", runtime.respond_node)

    g.add_edge(START, "route")
    g.add_conditional_edges(
        "route",
        lambda s: "tool_exec" if s["route"] == "metadata_query" else "retrieve",
        {"retrieve": "retrieve", "tool_exec": "tool_exec"},
    )
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges(
        "grade", runtime.grade_branch, {"generate": "generate", "rewrite": "rewrite", "abstain": "abstain"}
    )
    g.add_edge("rewrite", "retrieve")
    g.add_edge("tool_exec", "generate")
    g.add_edge("generate", "verify")
    g.add_conditional_edges(
        "verify",
        runtime.verify_branch,
        {"respond": "respond", "save_report": "save_report", "regenerate": "regenerate", "abstain": "abstain"},
    )
    g.add_edge("regenerate", "generate")
    g.add_edge("save_report", "respond")
    g.add_edge("abstain", "respond")
    g.add_edge("respond", END)
    return g.compile(checkpointer=checkpointer)
