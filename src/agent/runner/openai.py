"""
OpenAI Agents SDK 기반 runner.

Agent + Runner.run()으로 MCP 도구 연결 및 LLM 호출을 수행하고,
결과를 IAgent 인터페이스 형태로 반환한다.
"""

import re
from contextlib import AsyncExitStack

from agents import Agent, Runner, RunConfig, ModelSettings, MessageOutputItem

from src.agent.base import IAgent, AgentResult
from src.agent.usage import RequestUsage, TurnUsage


class OpenAIAgent(IAgent):
    """OpenAI Agents SDK 기반 IAgent 구현체."""

    def __init__(self, agent_name: str, sdk_agent: Agent, max_tokens: int = 8096) -> None:
        self._name = agent_name
        self._sdk_agent = sdk_agent
        self._max_tokens = max_tokens

    @property
    def name(self) -> str:
        return self._name

    @property
    def provider(self) -> str:
        return "openai"

    async def run(self, message: str) -> AgentResult:
        """메시지를 받아 Agent를 실행하고 AgentResult를 반환한다."""
        run_config = RunConfig(
            model_settings=ModelSettings(max_tokens=self._max_tokens),
            tracing_disabled=True,
        )

        async with AsyncExitStack() as stack:
            await self._connect_mcp_servers(self._sdk_agent, stack)
            result = await Runner.run(
                starting_agent=self._sdk_agent,
                input=message,
                run_config=run_config,
                max_turns=30,
            )

        turns = self._collect_turns(result)
        usage = self._build_usage(turns)
        return AgentResult(
            output=self._extract_output(result),
            usage=usage,
            turns=turns,
            raw=result,
        )

    @staticmethod
    def _collect_turns(result) -> list[TurnUsage]:
        """new_items의 agent 순서와 raw_responses를 매핑해 turn별 사용량을 수집한다."""
        agent_names = [
            item.agent.name
            for item in result.new_items
            if isinstance(item, MessageOutputItem)
        ]

        turns = []
        for i, response in enumerate(result.raw_responses):
            if not response.usage:
                continue
            agent_name = agent_names[i] if i < len(agent_names) else "unknown"
            model = str(
                getattr(response, "model", None)
                or getattr(response, "model_id", None)
                or "unknown"
            )
            turns.append(TurnUsage(
                agent_name=agent_name,
                model=model,
                input_tokens=response.usage.input_tokens or 0,
                output_tokens=response.usage.output_tokens or 0,
            ))
        return turns

    @staticmethod
    def _build_usage(turns: list[TurnUsage]) -> RequestUsage:
        """TurnUsage 목록에서 모델별 RequestUsage를 집계한다."""
        usage = RequestUsage()
        for turn in turns:
            usage.add(
                model=turn.model,
                input_tokens=turn.input_tokens,
                output_tokens=turn.output_tokens,
            )
        return usage

    @staticmethod
    def _extract_output(result) -> str:
        """RunResult에서 최종 텍스트 응답을 추출한다."""
        if result.final_output is not None:
            return str(result.final_output)

        for item in reversed(result.new_items):
            if isinstance(item, MessageOutputItem):
                raw = item.raw_item
                if hasattr(raw, "content") and isinstance(raw.content, list):
                    texts = [part.text for part in raw.content if hasattr(part, "text")]
                    if texts:
                        return "\n".join(texts)
        return ""

    async def _connect_mcp_servers(
        self, agent: Agent, stack: AsyncExitStack, visited: set[int] | None = None
    ) -> None:
        """Agent와 모든 handoff Agent의 MCP 서버를 재귀적으로 연결한다.

        visited로 순환 참조를 방지한다.
        """
        if visited is None:
            visited = set()
        if id(agent) in visited:
            return
        visited.add(id(agent))

        for server in (agent.mcp_servers or []):
            await stack.enter_async_context(server)
        for handoff in (agent.handoffs or []):
            if isinstance(handoff, Agent):
                await self._connect_mcp_servers(handoff, stack, visited)


class OrchestratorAgent(OpenAIAgent):
    """handoff 없이 orchestrator가 Runner.run()으로 sub-agents를 직접 순차 호출한다."""

    _TARGET_RE = re.compile(r'\[다음 대상\]\s*\n(.+?)(?=\n\[|\Z)', re.DOTALL)
    _CONTEXT_RE = re.compile(r'\[전달할 컨텍스트\]\s*\n(.+?)(?=\n\[|\Z)', re.DOTALL)
    _FINAL_TARGET = "user"

    def __init__(
        self,
        agent_name: str,
        orchestrator: Agent,
        sub_agents: dict[str, Agent],
        max_tokens: int = 8096,
        max_turns: int = 30,
        max_iterations: int = 10,
    ) -> None:
        super().__init__(agent_name, orchestrator, max_tokens)
        self._sub_agents = sub_agents
        self._max_turns = max_turns
        self._max_iterations = max_iterations

    async def run(self, message: str) -> AgentResult:
        """오케스트레이터 루프: sub-agent를 Runner.run()으로 순차 실행한다."""
        run_config = RunConfig(
            model_settings=ModelSettings(max_tokens=self._max_tokens),
            tracing_disabled=True,
        )
        all_turns: list[TurnUsage] = []
        context = message
        last_result = None

        async with AsyncExitStack() as stack:
            connected: set[int] = set()
            for agent in [self._sdk_agent, *self._sub_agents.values()]:
                for server in (agent.mcp_servers or []):
                    if id(server) not in connected:
                        await stack.enter_async_context(server)
                        connected.add(id(server))

            for _ in range(self._max_iterations):
                orch_result = await Runner.run(
                    starting_agent=self._sdk_agent,
                    input=context,
                    run_config=run_config,
                    max_turns=self._max_turns,
                )
                all_turns.extend(self._collect_turns(orch_result))
                last_result = orch_result

                output = self._extract_output(orch_result)
                next_target, next_context = self._parse_decision(output)

                if next_target == self._FINAL_TARGET:
                    return AgentResult(
                        output=next_context,
                        usage=self._build_usage(all_turns),
                        turns=all_turns,
                        raw=orch_result,
                    )

                sub_agent = self._sub_agents.get(next_target)
                if sub_agent is None:
                    break

                sub_result = await Runner.run(
                    starting_agent=sub_agent,
                    input=next_context,
                    run_config=run_config,
                    max_turns=self._max_turns,
                )
                all_turns.extend(self._collect_turns(sub_result))
                context = (
                    f"[원래 요청]\n{message}\n\n"
                    f"[{next_target} 실행 결과]\n{self._extract_output(sub_result)}"
                )

        return AgentResult(
            output=self._extract_output(last_result) if last_result else "",
            usage=self._build_usage(all_turns),
            turns=all_turns,
            raw=last_result,
        )

    @classmethod
    def _parse_decision(cls, output: str) -> tuple[str, str]:
        """오케스트레이터 출력에서 [다음 대상]과 [전달할 컨텍스트]를 추출한다."""
        target_match = cls._TARGET_RE.search(output)
        context_match = cls._CONTEXT_RE.search(output)
        target = target_match.group(1).strip() if target_match else cls._FINAL_TARGET
        context = context_match.group(1).strip() if context_match else output
        return target, context