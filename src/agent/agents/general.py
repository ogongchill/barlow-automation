"""
General-purpose assistant agent. No GitHub access.
"""

from src.agent.base import AgentConfig
from src.agent.tools import build_server

SYSTEM_PROMPT = """You are a helpful Slack bot assistant.
Answer concisely and clearly. Use Korean if the user writes in Korean."""

_LOCAL_TOOLS = [
    "mcp__local__get_current_time",
]


def create() -> AgentConfig:
    return AgentConfig(
        name="general",
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=list(_LOCAL_TOOLS),
        mcp_servers={"local": build_server()},
    )
