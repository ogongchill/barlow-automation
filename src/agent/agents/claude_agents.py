from src.agent.agents.agent_info import AvailableAgents
from src.agent.agents.github import _GITHUB_TREE_READ_TOOLS
from src.agent.runner.claude import ClaudeAgent
from src.agent.runner.models import Model
from src.config import config


def create() -> ClaudeAgent:
    return ClaudeSdkAgents.create()


class ClaudeSdkAgents:

    @classmethod
    def _github_mcp(cls) -> dict:
        return {
            "github": {
                "type": "http",
                "url": "https://api.githubcopilot.com/mcp/",
                "headers": {
                    "Authorization": config.github_token,
                    "X-MCP-Tools": ", ".join(_GITHUB_TREE_READ_TOOLS),
                    "X-MCP-Readonly": "true",
                },
            }
        }

    @classmethod
    def create(cls) -> ClaudeAgent:
        read_planner_info = AvailableAgents.READ_PLANNER.value
        return ClaudeAgent(
            agent_name=read_planner_info.name,
            system_prompt=read_planner_info.sys_prompt,
            model=Model.Claude.HAIKU_3.name,
            mcp_servers=cls._github_mcp(),
            output_type=read_planner_info.output_format,
        )
