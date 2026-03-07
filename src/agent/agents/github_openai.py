"""
GitHub-capable agent (OpenAI Codex). Read-only GitHub MCP tools.
"""

from src.agent.base import IAgent
from src.agent.runner.models import Model
from src.agent.runner.openai import OpenAIAgentConfig, OpenAIAgent
from src.config import config, OsType

SYSTEM_PROMPT = """You are a GitHub code analysis assistant connected to live GitHub repositories.

RULES (must follow without exception):
1. ALWAYS use GitHub tools to answer questions about code, repositories, files, or PRs.
2. NEVER answer from memory or training data about repository contents.
3. If the user does not specify a repository, ask for the owner/repo before proceeding.
4. After retrieving data with tools, summarize findings based solely on the retrieved content.
5. If a tool call fails, report the error clearly instead of guessing.

Use Korean if the user writes in Korean."""


def create() -> IAgent:
    """Codex 모델 기반 GitHub 분석 Agent를 생성한다."""
    npx_cmd = "npx.cmd" if config.os_type == OsType.WINDOWS else "npx"

    cfg = OpenAIAgentConfig(
        system_prompt=SYSTEM_PROMPT,
        model=Model.GPT.CODEX_5_3,
        max_tokens=8096,
        mcp_servers={
            "github": {
                "command": npx_cmd,
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": config.github_token},
            }
        },
    )
    return OpenAIAgent("github-openai", cfg)
