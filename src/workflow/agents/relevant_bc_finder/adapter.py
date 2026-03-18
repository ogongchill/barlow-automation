"""RELEVANT_BC_FINDER agent output adapter."""

from src.agent.base import AgentResult


def to_bc_candidates_json(agent_result: AgentResult) -> str:
    """AgentResult.output (JSON str) to workflow contract string."""
    return agent_result.output
