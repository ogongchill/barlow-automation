"""역할별 OpenAI Agent를 생성하는 팩토리 클래스."""

from agents import Agent

from src.agent.agents.agent_info import AvailableAgents
from src.agent.agents.github import GitHubMCPFactory
from src.agent.runner.models import Model
from src.agent.runner.openai import OpenAIAgent


class OpenAiAgentFactory:

    @staticmethod
    def read_planner() -> OpenAIAgent:
        info = AvailableAgents.READ_PLANNER.value
        return OpenAIAgent(
            agent_name=info.name,
            sdk_agent=Agent(
                name=info.name,
                instructions=info.sys_prompt,
                model=Model.GPT.GPT_5_MINI.name,
                mcp_servers=[GitHubMCPFactory.readProjectTree()],
                output_type=info.output_format,
            ),
        )

    @staticmethod
    def file_tree_insepctor() -> OpenAIAgent:
        info = AvailableAgents.READ_TARGET_INSPECTOR.value
        return OpenAIAgent(
            agent_name=info.name,
            sdk_agent=Agent(
                name=info.name,
                instructions=info.sys_prompt,
                model=Model.GPT.GPT_5_MINI.name,
                mcp_servers=[GitHubMCPFactory.readProjectTree()],
                output_type=info.output_format,
            ),
        )

    @staticmethod
    def feat_issue_gen() -> OpenAIAgent:
        info = AvailableAgents.FEAT_ISSUE_GEN.value
        return OpenAIAgent(
            agent_name=info.name,
            sdk_agent=Agent(
                name=info.name,
                instructions=info.sys_prompt,
                model=Model.GPT.GPT_5_MINI.name,
                mcp_servers=[GitHubMCPFactory.readProject()],
                output_type=info.output_format,
            ),
        )

    @staticmethod
    def refactor_issue_gen() -> OpenAIAgent:
        info = AvailableAgents.REFACTOR_ISSUE_GEN.value
        return OpenAIAgent(
            agent_name=info.name,
            sdk_agent=Agent(
                name=info.name,
                instructions=info.sys_prompt,
                model=Model.GPT.GPT_5_MINI.name,
                mcp_servers=[GitHubMCPFactory.readProject()],
                output_type=info.output_format,
            ),
        )

    @staticmethod
    def fix_issue_gen() -> OpenAIAgent:
        info = AvailableAgents.FIX_ISSUE_GEN.value
        return OpenAIAgent(
            agent_name=info.name,
            sdk_agent=Agent(
                name=info.name,
                instructions=info.sys_prompt,
                model=Model.GPT.GPT_5_MINI.name,
                mcp_servers=[GitHubMCPFactory.readProject()],
                output_type=info.output_format,
            ),
        )

    @staticmethod
    def feat_reissue_gen() -> OpenAIAgent:
        info = AvailableAgents.FEAT_REISSUE_GEN.value
        return OpenAIAgent(
            agent_name=info.name,
            sdk_agent=Agent(
                name=info.name,
                instructions=info.sys_prompt,
                model=Model.GPT.GPT_5_MINI.name,
                mcp_servers=[GitHubMCPFactory.readProject()],
                output_type=info.output_format,
            ),
        )

    @staticmethod
    def refactor_reissue_gen() -> OpenAIAgent:
        info = AvailableAgents.REFACTOR_REISSUE_GEN.value
        return OpenAIAgent(
            agent_name=info.name,
            sdk_agent=Agent(
                name=info.name,
                instructions=info.sys_prompt,
                model=Model.GPT.GPT_5_MINI.name,
                mcp_servers=[GitHubMCPFactory.readProject()],
                output_type=info.output_format,
            ),
        )

    @staticmethod
    def fix_reissue_gen() -> OpenAIAgent:
        info = AvailableAgents.FIX_REISSUE_GEN.value
        return OpenAIAgent(
            agent_name=info.name,
            sdk_agent=Agent(
                name=info.name,
                instructions=info.sys_prompt,
                model=Model.GPT.GPT_5_MINI.name,
                mcp_servers=[GitHubMCPFactory.readProject()],
                output_type=info.output_format,
            ),
        )
