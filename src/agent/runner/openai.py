from agents import Agent, Runner, RunConfig, ModelSettings, MessageOutputItem

from src.agent.base import IAgent, AgentResult
from src.agent.usage import AgentUsage


class OpenAIAgent(IAgent):

    def __init__(
        self,
        agent_name: str,
        sdk_agent: Agent,
        max_tokens: int = 8096
    ) -> None:
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
        result = await Runner.run(
            starting_agent=self._sdk_agent,
            input=message,
            run_config=run_config,
            max_turns=30,
        )
        usage = result.context_wrapper.usage
        agent_usage = AgentUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        return AgentResult(
            output=self._extract_output(result),
            usage=agent_usage,
            raw=result,
        )

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
