"""FEAT_ISSUE_GEN agent output adapter."""

from src.agent.base import AgentResult


def to_issue_draft_json(agent_result: AgentResult) -> str:
    """typed_output (FeatTemplate) to JSON string."""
    if agent_result.typed_output is not None:
        return agent_result.typed_output.model_dump_json()
    return agent_result.output
