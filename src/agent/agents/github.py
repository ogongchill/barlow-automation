"""
GitHub-capable agent (Claude). Read-only GitHub MCP tools.
"""

from src.agent.base import IAgent
# from src.agent.runner.claude import ClaudeAgentConfig, ClaudeAgent
from src.agent.tools import build_server
from src.config import config

SYSTEM_PROMPT = """You are a helpful Slack bot assistant with access to GitHub repositories.
You can read files, search code, browse branches, and inspect pull requests.
Answer concisely and clearly. Use Korean if the user writes in Korean."""

_LOCAL_TOOLS = [
    "mcp__local__get_current_time",
]

_GITHUB_READ_TOOLS = [
    "mcp__github__get_file_contents",
    "mcp__github__get_repository",
    "mcp__github__list_branches",
    # "mcp__github__list_commits",
    # "mcp__github__get_commit",
    # "mcp__github__list_issues",
    # "mcp__github__get_issue",
    # "mcp__github__list_issue_comments",
    # "mcp__github__list_pull_requests",
    # "mcp__github__get_pull_request",
    # "mcp__github__get_pull_request_diff",
    "mcp__github__get_pull_request_files",
    # "mcp__github__get_pull_request_reviews",
    "mcp__github__search_repositories",
    "mcp__github__search_code",
    # "mcp__github__search_issues",
]


def create() -> IAgent:
    mcp_servers = {"local": build_server()}
    allowed_tools = list(_LOCAL_TOOLS)

    if config.github_token:
        mcp_servers["github"] = {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": config.github_token},
        }
        allowed_tools.extend(_GITHUB_READ_TOOLS)

    # cfg = ClaudeAgentConfig(
    #     system_prompt=SYSTEM_PROMPT,
    #     allowed_tools=allowed_tools,
    #     mcp_servers=mcp_servers,
    # )
    # return ClaudeAgent("github", cfg)
