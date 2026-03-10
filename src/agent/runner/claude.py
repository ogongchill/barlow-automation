"""Claude Agent SDK 기반 runner."""

import json
from typing import Any

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, AssistantMessage, TextBlock
from claude_agent_sdk.types import McpServerConfig
from pydantic import BaseModel

from src.agent.base import IAgent, AgentResult
from src.agent.usage import RequestUsage


class ClaudeAgent(IAgent):

    def __init__(
        self,
        agent_name: str,
        system_prompt: str,
        model: str,
        mcp_servers: dict[str, McpServerConfig] | None = None,
        output_type: type[BaseModel] | None = None,
        max_turns: int = 30,
    ) -> None:
        self._name = agent_name
        self._system_prompt = system_prompt
        self._model = model
        self._mcp_servers: dict[str, McpServerConfig] = mcp_servers or {}
        self._output_type = output_type
        self._max_turns = max_turns

    @property
    def name(self) -> str:
        return self._name

    @property
    def provider(self) -> str:
        return "anthropic"

    async def run(self, message: str) -> AgentResult:
        output_format: dict[str, Any] | None = None
        if self._output_type is not None:
            output_format = {
                "type": "json_schema",
                "schema": self._output_type.model_json_schema(),
            }

        options = ClaudeAgentOptions(
            system_prompt=self._system_prompt,
            model=self._model,
            mcp_servers=self._mcp_servers,
            permission_mode="bypassPermissions",
            max_turns=self._max_turns,
            output_format=output_format,
        )

        result_msg: ResultMessage | None = None
        last_text: str = ""

        async for msg in query(prompt=message, options=options):
            if isinstance(msg, ResultMessage):
                result_msg = msg
            elif isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        last_text = block.text

        usage = RequestUsage()
        if result_msg is not None:
            if result_msg.usage:
                usage.add_from_api(
                    model=self._model,
                    usage=result_msg.usage,
                    actual_cost_usd=result_msg.total_cost_usd,
                )
            output = self._extract_output(result_msg, last_text)
        else:
            output = last_text

        return AgentResult(output=output, usage=usage, raw=result_msg)

    @staticmethod
    def _extract_output(result_msg: ResultMessage, fallback: str) -> str:
        if result_msg.structured_output is not None:
            raw = result_msg.structured_output
            return json.dumps(raw, ensure_ascii=False) if not isinstance(raw, str) else raw
        if result_msg.result:
            return result_msg.result
        return fallback
