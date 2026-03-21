"""refactor 워크플로우 전용 Agent 빌드 팩토리."""

from enum import Enum

from agents import Agent

from src.agent.mcp import GitHubMCPFactory
from src.agent.models import Model
from src.agent.openai import OpenAIAgent
from src.domain.feat.agents.relevant_bc_finder.prompt import SYSTEM_PROMPT as BC_FINDER_PROMPT
from src.domain.feat.agents.relevant_bc_finder.schema import Candidates
from src.domain.refactor.agents.issue_generator.prompt import SYSTEM_PROMPT as ISSUE_GEN_PROMPT
from src.domain.refactor.agents.issue_generator.schema import RefactorTemplate
from src.domain.refactor.agents.issue_regenerator.prompt import SYSTEM_PROMPT as ISSUE_REGEN_PROMPT


class RefactorAgentKey(str, Enum):
    RELEVANT_BC_FINDER = "relevant_bc_finder"
    ISSUE_GEN = "refactor_issue_gen"
    ISSUE_REGEN = "refactor_reissue_gen"


class RefactorAgentExecutor:

    @staticmethod
    def build(key: RefactorAgentKey) -> OpenAIAgent:
        _MAP = {
            RefactorAgentKey.RELEVANT_BC_FINDER: (BC_FINDER_PROMPT, Candidates, GitHubMCPFactory.readProjectTree),
            RefactorAgentKey.ISSUE_GEN: (ISSUE_GEN_PROMPT, RefactorTemplate, GitHubMCPFactory.readProject),
            RefactorAgentKey.ISSUE_REGEN: (ISSUE_REGEN_PROMPT, RefactorTemplate, GitHubMCPFactory.readProject),
        }
        if key not in _MAP:
            raise KeyError(f"Unknown RefactorAgentKey: {key}")
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
