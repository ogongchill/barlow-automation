"""
GitHub MCP 없이 동작하는 범용 Agent (OpenAI 기반).
"""

from src.agent.base import IAgent
from src.agent.runner.models import Model
from src.agent.runner.openai import OpenAIAgentConfig, OpenAIAgent

SYSTEM_PROMPT = """You are a helpful Slack bot assistant.
Answer concisely and clearly. Use Korean if the user writes in Korean."""


def create() -> IAgent:
    """MCP 없이 동작하는 범용 Agent를 생성한다."""
    cfg = OpenAIAgentConfig(
        system_prompt=SYSTEM_PROMPT,
        model=Model.GPT.DEFAULT,
    )
    return OpenAIAgent("general", cfg)
