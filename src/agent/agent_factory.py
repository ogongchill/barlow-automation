"""역할별 OpenAI Agent를 생성하는 팩토리 클래스."""

from agents import Agent

from src.agent.agent_info import AvailableAgents
from src.agent.mcp import GitHubMCPFactory
from src.agent.models import Model
from src.agent.openai import OpenAIAgent


class AgentFactory:

    @staticmethod
    def _build(key: AvailableAgents, mcp_server) -> OpenAIAgent:
        info = key.value
        return OpenAIAgent(
            agent_name=info.name,
            sdk_agent=Agent(
                name=info.name,
                instructions=info.sys_prompt,
                model=Model.GPT.GPT_5_MINI.name,
                mcp_servers=[mcp_server],
                output_type=info.output_format,
            ),
        )

    @staticmethod
    def inspector() -> OpenAIAgent:
        return AgentFactory._build(
            AvailableAgents.READ_TARGET_INSPECTOR,
            GitHubMCPFactory.readProjectTree()
        )

    @staticmethod
    def issue_gen(subcommand: str) -> OpenAIAgent:
        key = {
            "feat": AvailableAgents.FEAT_ISSUE_GEN,
            "refactor": AvailableAgents.REFACTOR_ISSUE_GEN,
            "fix": AvailableAgents.FIX_ISSUE_GEN,
        }[subcommand]
        return AgentFactory._build(key, GitHubMCPFactory.readProject())

    @staticmethod
    def reissue_gen(subcommand: str) -> OpenAIAgent:
        key = {
            "feat": AvailableAgents.FEAT_REISSUE_GEN,
            "refactor": AvailableAgents.REFACTOR_REISSUE_GEN,
            "fix": AvailableAgents.FIX_REISSUE_GEN,
        }[subcommand]
        return AgentFactory._build(key, GitHubMCPFactory.readProject())

    @staticmethod
    def issue_writer(subcommand: str) -> OpenAIAgent:
        key = {
            "feat": AvailableAgents.FEAT_ISSUE_WRITER,
            "refactor": AvailableAgents.REFACTOR_ISSUE_WRITER,
            "fix": AvailableAgents.FIX_ISSUE_WRITER,
        }[subcommand]
        return AgentFactory._build(key, GitHubMCPFactory.writeIssue())
