"""AgentExecutor -- agent build factory (AgentFactory role successor)."""

from enum import Enum

from agents import Agent

from src.agent.mcp import GitHubMCPFactory
from src.agent.models import Model
from src.agent.openai import OpenAIAgent


class AgentKey(str, Enum):
    RELEVANT_BC_FINDER = "relevant_bc_finder"
    FEAT_ISSUE_GEN = "feat_issue_gen"
    REFACTOR_ISSUE_GEN = "refactor_issue_gen"
    FIX_ISSUE_GEN = "fix_issue_gen"
    FEAT_REISSUE_GEN = "feat_reissue_gen"
    REFACTOR_REISSUE_GEN = "refactor_reissue_gen"
    FIX_REISSUE_GEN = "fix_reissue_gen"


class AgentExecutor:

    @staticmethod
    def build(key: AgentKey) -> OpenAIAgent:
        """AgentKey에 해당하는 OpenAIAgent를 빌드하여 반환한다."""
        from src.agent.agent_info import AvailableAgents

        _KEY_MAP: dict[AgentKey, tuple[AvailableAgents, object]] = {
            AgentKey.RELEVANT_BC_FINDER: (AvailableAgents.RELEVANT_BC_FINDER, GitHubMCPFactory.readProjectTree),
            AgentKey.FEAT_ISSUE_GEN: (AvailableAgents.FEAT_ISSUE_GEN, GitHubMCPFactory.readProject),
            AgentKey.REFACTOR_ISSUE_GEN: (AvailableAgents.REFACTOR_ISSUE_GEN, GitHubMCPFactory.readProject),
            AgentKey.FIX_ISSUE_GEN: (AvailableAgents.FIX_ISSUE_GEN, GitHubMCPFactory.readProject),
            AgentKey.FEAT_REISSUE_GEN: (AvailableAgents.FEAT_REISSUE_GEN, GitHubMCPFactory.readProject),
            AgentKey.REFACTOR_REISSUE_GEN: (AvailableAgents.REFACTOR_REISSUE_GEN, GitHubMCPFactory.readProject),
            AgentKey.FIX_REISSUE_GEN: (AvailableAgents.FIX_REISSUE_GEN, GitHubMCPFactory.readProject),
        }

        if key not in _KEY_MAP:
            raise KeyError(f"Unknown AgentKey: {key}")

        agent_enum, mcp_factory = _KEY_MAP[key]
        info = agent_enum.value
        return OpenAIAgent(
            agent_name=info.name,
            sdk_agent=Agent(
                name=info.name,
                instructions=info.sys_prompt,
                model=Model.GPT.GPT_5_MINI.name,
                mcp_servers=[mcp_factory()],
                output_type=info.output_format,
            ),
        )
