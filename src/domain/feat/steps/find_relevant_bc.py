"""find_relevant_bc -- RELEVANT_BC_FINDER agent execution."""

from dataclasses import dataclass

from src.domain.feat.executor import (
    FeatAgentExecutor,
    FeatAgentKey,
)


@dataclass(frozen=True)
class FindRelevantBcInput:
    user_message: str


@dataclass(frozen=True)
class FindRelevantBcOutput:
    bc_candidates: str
    internal_trace: dict | None = None


class FindRelevantBcStep:

    async def execute(self, input: FindRelevantBcInput) -> FindRelevantBcOutput:
        agent = FeatAgentExecutor.build(FeatAgentKey.RELEVANT_BC_FINDER)
        result = await agent.run(input.user_message)
        return FindRelevantBcOutput(
            bc_candidates=result.output,
            internal_trace={
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
            },
        )
