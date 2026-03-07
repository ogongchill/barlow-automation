"""
OpenAI Agents SDK 기반 runner.

Agent + Runner.run()으로 MCP 도구 연결 및 LLM 호출을 수행하고,
결과를 IAgent 인터페이스 형태로 반환한다.
"""

from contextlib import AsyncExitStack
from dataclasses import dataclass, field

from agents import Agent, Runner, RunConfig, ModelSettings
from agents.mcp import MCPServerStdio

from src.agent.base import IAgent
from src.agent.runner.models import ModelConfig, Model
from src.agent.usage import RequestUsage


@dataclass
class OpenAIAgentConfig:
    """OpenAI Agent 생성에 필요한 설정 묶음."""
    system_prompt: str
    model: ModelConfig = field(default_factory=lambda: Model.GPT.DEFAULT)
    max_tokens: int = 8096
    mcp_servers: dict[str, dict] = field(default_factory=dict)


class OpenAIAgent(IAgent):
    """OpenAI Agents SDK 기반 IAgent 구현체."""

    def __init__(self, agent_name: str, config: OpenAIAgentConfig) -> None:
        self._name = agent_name
        self._config = config

    @property
    def name(self) -> str:
        return self._name

    @property
    def provider(self) -> str:
        return "openai"

    async def run(self, message: str) -> tuple[str, RequestUsage]:
        """메시지를 받아 Agent를 실행하고 (응답 텍스트, 사용량) 튜플을 반환한다."""
        run_config = RunConfig(
            model_settings=ModelSettings(max_tokens=self._config.max_tokens, tool_choice="required"),
            tracing_disabled=True,
        )

        async with AsyncExitStack() as stack:
            mcp_servers = [
                await stack.enter_async_context(server)
                for server in self._build_mcp_servers()
            ]

            agent = Agent(
                name=self._name,
                instructions=self._config.system_prompt,
                model=self._config.model.name,
                mcp_servers=mcp_servers,
            )

            result = await Runner.run(
                starting_agent=agent,
                input=message,
                run_config=run_config,
                max_turns=30,
            )

        return self._extract_output(result), self._extract_usage(result)

    def _build_mcp_servers(self) -> list[MCPServerStdio]:
        """설정된 MCP 서버 정의를 MCPServerStdio 인스턴스 목록으로 변환한다."""
        servers: list[MCPServerStdio] = []
        for name, server_def in self._config.mcp_servers.items():
            server = MCPServerStdio(
                params={
                    "command": server_def["command"],
                    "args": server_def.get("args", []),
                    "env": server_def.get("env"),
                },
                name=name,
                cache_tools_list=True,
                client_session_timeout_seconds=60,
            )
            servers.append(server)
        return servers

    @staticmethod
    def _extract_output(result) -> str:
        """RunResult에서 최종 텍스트 응답을 추출한다."""
        if result.final_output is not None:
            return str(result.final_output)

        # final_output이 None인 경우 new_items에서 마지막 메시지를 추출
        from agents import MessageOutputItem
        for item in reversed(result.new_items):
            if isinstance(item, MessageOutputItem):
                raw = item.raw_item
                if hasattr(raw, "content") and isinstance(raw.content, list):
                    texts = []
                    for part in raw.content:
                        if hasattr(part, "text"):
                            texts.append(part.text)
                    if texts:
                        return "\n".join(texts)
        return ""

    def _extract_usage(self, result) -> RequestUsage:
        """RunResult.raw_responses에서 토큰 사용량을 집계한다."""
        usage = RequestUsage()

        total_input = 0
        total_output = 0

        for response in result.raw_responses:
            if response.usage:
                total_input += response.usage.input_tokens or 0
                total_output += response.usage.output_tokens or 0

        if total_input or total_output:
            usage.set_result(
                model=self._config.model.name,
                usage={
                    "input_tokens": total_input,
                    "output_tokens": total_output,
                },
                total_cost_usd=None,
            )

        return usage
