"""
Generic agent runner.

AgentConfig defines *what* an agent is (identity, prompt, tools).
run() defines *how* it executes (message loop, usage tracking).
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TaskStartedMessage,
    TaskProgressMessage,
    TaskNotificationMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    ToolResultBlock,
    UserMessage,
)

from src.agent.usage import RequestUsage

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """에이전트의 역할을 정의하는 불변 설정 객체."""

    name: str
    system_prompt: str
    allowed_tools: list[str] = field(default_factory=list)
    mcp_servers: dict[str, Any] = field(default_factory=dict)

    def build_options(self) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            system_prompt=self.system_prompt,
            mcp_servers=self.mcp_servers,
            allowed_tools=self.allowed_tools,
        )


# ---------------------------------------------------------------------------
# Message handlers (stateless helpers)
# ---------------------------------------------------------------------------

def _on_assistant(message: AssistantMessage) -> str:
    last_text = ""
    if message.error:
        logger.warning("[%s] assistant error | %s", message.model, message.error)

    for block in message.content:
        if isinstance(block, TextBlock):
            last_text = block.text
        elif isinstance(block, ToolUseBlock):
            logger.info("tool_use | name=%s id=%s", block.name, block.id)
        elif isinstance(block, ThinkingBlock):
            logger.debug("thinking | len=%d", len(block.thinking))
        elif isinstance(block, ToolResultBlock):
            logger.debug("tool_result | tool_use_id=%s", block.tool_use_id)

    return last_text


def _on_result(message: ResultMessage, model: str, usage: RequestUsage) -> None:
    if message.usage:
        usage.set_result(model, message.usage, message.total_cost_usd)

    logger.info(
        "result | turns=%d duration=%dms cost=$%.5f is_error=%s",
        message.num_turns,
        message.duration_ms,
        message.total_cost_usd or 0.0,
        message.is_error,
    )


def _on_system(message: SystemMessage) -> None:
    if isinstance(message, TaskStartedMessage):
        logger.info("task started | id=%s desc=%r", message.task_id, message.description)
    elif isinstance(message, TaskProgressMessage):
        logger.info(
            "task progress | id=%s tool=%s total_tokens=%d",
            message.task_id,
            message.last_tool_name,
            message.usage.get("total_tokens", 0),
        )
    elif isinstance(message, TaskNotificationMessage):
        logger.info("task notification | id=%s status=%s", message.task_id, message.status)
    else:
        logger.debug("system | subtype=%s", message.subtype)


# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------

async def run(agent: AgentConfig, user_message: str) -> tuple[str, RequestUsage]:
    logger.info("agent=%s start | message=%r", agent.name, user_message)
    options = agent.build_options()
    usage = RequestUsage()
    last_text = ""
    last_model = ""

    async for message in query(prompt=user_message, options=options):
        if isinstance(message, AssistantMessage):
            last_model = message.model
            text = _on_assistant(message)
            if text:
                last_text = text

        elif isinstance(message, ResultMessage):
            _on_result(message, last_model, usage)

        elif isinstance(message, SystemMessage):
            _on_system(message)

        elif isinstance(message, UserMessage):
            pass  # 유저 입력 에코, 무시

        else:
            logger.debug("unhandled message type | %s", type(message).__name__)

    logger.info(
        "agent=%s done | input=%d output=%d cost=$%.5f",
        agent.name, usage.total_input, usage.total_output, usage.total_cost,
    )
    return last_text or "응답을 처리하는 중 오류가 발생했습니다.", usage
