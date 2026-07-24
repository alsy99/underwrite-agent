"""
LangGraph investigation state machine.

Stages: intake → cross_check → policy_rag → plan → agent_loop → synthesize → finalize
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from packages.schemas.case import Contradiction, PolicyFinding


class InvestigationState(TypedDict, total=False):
    case_id: str
    tenant_id: str
    vertical: str
    metadata: dict[str, Any]
    document_bundle: str
    contradictions: list[Contradiction]
    policy_findings: list[PolicyFinding]
    plan: list[tuple[str, dict[str, Any]]]
    tool_results: list[dict[str, Any]]
    executive_summary: str
    case_file: dict[str, Any]
    step_count: int
    timeline: list[dict[str, Any]]
    open_questions: list[str]
    findings_extra: list[dict[str, Any]]


GRAPH_STAGES = [
    "intake",
    "cross_check",
    "policy_rag",
    "plan_investigation",
    "agent_loop",
    "synthesize_brief",
    "finalize",
]


def build_investigation_graph(runner: Any):
    """Compile a LangGraph StateGraph bound to an InvestigationRunner instance."""

    async def intake(state: InvestigationState) -> InvestigationState:
        return await runner.node_intake(state)

    async def cross_check(state: InvestigationState) -> InvestigationState:
        return await runner.node_cross_check(state)

    async def policy_rag(state: InvestigationState) -> InvestigationState:
        return await runner.node_policy_rag(state)

    async def plan_investigation(state: InvestigationState) -> InvestigationState:
        return await runner.node_plan(state)

    async def agent_loop(state: InvestigationState) -> InvestigationState:
        return await runner.node_agent_loop(state)

    async def synthesize_brief(state: InvestigationState) -> InvestigationState:
        return await runner.node_synthesize(state)

    async def finalize(state: InvestigationState) -> InvestigationState:
        return await runner.node_finalize(state)

    graph = StateGraph(InvestigationState)
    graph.add_node("intake", intake)
    graph.add_node("cross_check", cross_check)
    graph.add_node("policy_rag", policy_rag)
    graph.add_node("plan_investigation", plan_investigation)
    graph.add_node("agent_loop", agent_loop)
    graph.add_node("synthesize_brief", synthesize_brief)
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "cross_check")
    graph.add_edge("cross_check", "policy_rag")
    graph.add_edge("policy_rag", "plan_investigation")
    graph.add_edge("plan_investigation", "agent_loop")
    graph.add_edge("agent_loop", "synthesize_brief")
    graph.add_edge("synthesize_brief", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()
