"""feat 워크플로우 전용 Agent 빌드 팩토리."""

from enum import Enum

from agents import Agent

from src.agent.mcp import GitHubMCPFactory
from src.agent.models import Model
from src.agent.openai import OpenAIAgent
from src.domain.feat.agents.relevant_bc_finder.prompt import SYSTEM_PROMPT as BC_FINDER_PROMPT
from src.domain.feat.agents.relevant_bc_finder.schema import Candidates
from src.domain.feat.agents.issue_generator.prompt import SYSTEM_PROMPT as ISSUE_GEN_PROMPT
from src.domain.feat.agents.issue_generator.schema import FeatTemplate
from src.domain.feat.agents.issue_regenerator.prompt import SYSTEM_PROMPT as ISSUE_REGEN_PROMPT
from src.domain.feat.agents.relevant_issue_finder.prompt import build_sys_prompt as _build_relevant_issue_prompt
from src.domain.feat.agents.relevant_issue_finder.schema import RelevantIssue


class FeatAgentKey(str, Enum):
    RELEVANT_BC_FINDER = "relevant_bc_finder"
    ISSUE_GEN = "feat_issue_gen"
    ISSUE_REGEN = "feat_reissue_gen"
    RELEVANT_ISSUE_FINDER = "relevant_issue_finder"


_MAP = {
    FeatAgentKey.RELEVANT_BC_FINDER: (
        BC_FINDER_PROMPT,
        Candidates,
        GitHubMCPFactory.readProjectTree,
    ),
    FeatAgentKey.ISSUE_GEN: (
        ISSUE_GEN_PROMPT,
        FeatTemplate,
        GitHubMCPFactory.readProject,
    ),
    FeatAgentKey.ISSUE_REGEN: (
        ISSUE_REGEN_PROMPT,
        FeatTemplate,
        GitHubMCPFactory.readProject,
    ),
    FeatAgentKey.RELEVANT_ISSUE_FINDER: (
        _build_relevant_issue_prompt(),
        RelevantIssue,
        GitHubMCPFactory.readIssues,
    ),
}


class FeatAgentExecutor:

    @staticmethod
    async def build(key: FeatAgentKey) -> OpenAIAgent:
        if key not in _MAP:
            raise KeyError(f"Unknown FeatAgentKey: {key}")
        prompt, output_type, mcp_getter = _MAP[key]
        server = await mcp_getter()  # lazy connect
        return OpenAIAgent(
            agent_name=key.value,
            sdk_agent=Agent(
                name=key.value,
                instructions=prompt,
                model=Model.GPT.GPT_5_MINI.name,
                mcp_servers=[server],
                output_type=output_type,
            ),
        )
