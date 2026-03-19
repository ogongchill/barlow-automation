"""find_relevant_bc -- RELEVANT_BC_FINDER agent execution."""

from src.domain.feat.executor import FeatAgentExecutor, FeatAgentKey
from src.domain.common.models.step_result import StepResult
from src.domain.feat.models.state import FeatIssueWorkflowState


class FindRelevantBcStep:

    async def execute(self, state: FeatIssueWorkflowState) -> StepResult:
        agent = FeatAgentExecutor.build(FeatAgentKey.RELEVANT_BC_FINDER)
        result = await agent.run(state.user_message)
        return StepResult(
            status="success",
            control_signal="continue",
            state_patch={"bc_candidates": result.output},
            internal_trace={
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
            },
        )
