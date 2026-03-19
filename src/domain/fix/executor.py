"""fix 워크플로우 전용 Agent 빌드 팩토리."""

from enum import Enum

from agents import Agent

from src.agent.mcp import GitHubMCPFactory
from src.agent.models import Model
from src.agent.openai import OpenAIAgent
from src.domain.feat.agents.relevant_bc_finder.prompt import SYSTEM_PROMPT as BC_FINDER_PROMPT
from src.domain.feat.agents.relevant_bc_finder.schema import Candidates
from src.domain.fix.agents.issue_generator.prompt import SYSTEM_PROMPT as ISSUE_GEN_PROMPT
from src.domain.fix.agents.issue_generator.schema import FixTemplate
from src.domain.fix.agents.issue_regenerator.prompt import SYSTEM_PROMPT as ISSUE_REGEN_PROMPT


class FixAgentKey(str, Enum):
    RELEVANT_BC_FINDER = "relevant_bc_finder"
    ISSUE_GEN = "fix_issue_gen"
    ISSUE_REGEN = "fix_reissue_gen"


class FixAgentExecutor:

    @staticmethod
    def build(key: FixAgentKey) -> OpenAIAgent:
        _MAP = {
            FixAgentKey.RELEVANT_BC_FINDER: (BC_FINDER_PROMPT, Candidates, GitHubMCPFactory.readProjectTree),
            FixAgentKey.ISSUE_GEN: (ISSUE_GEN_PROMPT, FixTemplate, GitHubMCPFactory.readProject),
            FixAgentKey.ISSUE_REGEN: (ISSUE_REGEN_PROMPT, FixTemplate, GitHubMCPFactory.readProject),
        }
        if key not in _MAP:
            raise KeyError(f"Unknown FixAgentKey: {key}")
        prompt, output_type, mcp_factory = _MAP[key]
        return OpenAIAgent(
            agent_name=key.value,
            sdk_agent=Agent(
                name=key.value,
                instructions=prompt,
                model=Model.GPT.GPT_5_MINI.name,
                mcp_servers=[mcp_factory()],
                output_type=output_type,
            ),
        )
