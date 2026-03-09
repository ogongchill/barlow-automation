from agents import Agent
from agents.mcp import MCPServer

from src.agent.runner.models import Model
from src.agent.runner.openai import OrchestratorAgent, OpenAIAgent
import src.agent.agents.github as github_mcp
from src.agent.agents.github import GitHubMCPFactory
from src.agent.agents.agent_info import AvailableAgents

def create() -> OrchestratorAgent:
    return OpenAiSdkAgents.create()


class OpenAiSdkAgents:

    @classmethod
    def _github_mcp(cls) -> MCPServer:
        return github_mcp.GITHUB_REMOTE_MCP

    @classmethod
    def create(cls) -> OrchestratorAgent:
        read_planner_info = AvailableAgents.READ_PLANNER.value
        read_planner = Agent(
            name=read_planner_info.name,
            instructions=read_planner_info.sys_prompt,
            model=Model.GPT.GPT_5_MINI.name,
            mcp_servers=[GitHubMCPFactory.readProjectTree()],
            output_type=read_planner_info.output_format
        )
        # reader = Agent(
        #     name="code_reader",
        #     instructions=Prompts.ANALYZER,
        #     model=Model.GPT.GPT_5_2.name,
        #     mcp_servers=[GitHubMCPFactory.readProject],
        # )
        # spec_gen = Agent(
        #     name="spec_gen",
        #     instructions=cls._spec_prompt,
        #     model=Model.GPT.GPT_5_2.name,
        #     mcp_servers=[GitHubMCPFactory.readProject],
        # )
        # orchestrator = Agent(
        #     name="orchestrator",
        #     instructions=cls._orechestrator_prompt,
        #     model=Model.GPT.GPT_5_2.name,
        # )
        # sub_agents = {
        #     "read_planner": reader_planner,
        #     "code_reader": reader,
        #     "spec_gen": spec_gen,
        # }
        return OpenAIAgent(
            agent_name=read_planner_info.name,
            sdk_agent=read_planner,
        )
    