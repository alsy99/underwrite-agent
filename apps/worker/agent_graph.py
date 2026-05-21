"""
LangGraph-style investigation graph (explicit state machine).

The MVP implements the same flow in InvestigationRunner; this module documents
the graph structure for future LangGraph SDK integration.
"""

from typing import TypedDict


class InvestigationState(TypedDict, total=False):
    case_id: str
    tenant_id: str
    vertical: str
    document_bundle: str
    contradictions: list
    policy_findings: list
    tool_results: list
    case_file: dict
    step_count: int


GRAPH_STAGES = [
    "intake",
    "doc_parse",
    "cross_check",
    "plan_investigation",
    "agent_loop",
    "synthesize_brief",
]
