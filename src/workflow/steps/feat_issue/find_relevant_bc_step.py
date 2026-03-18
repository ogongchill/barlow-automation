"""find_relevant_bc_step -- RELEVANT_BC_FINDER agent execution."""

from src.workflow.executors.agent_executor import AgentExecutor, AgentKey
from src.workflow.models.step_result import StepResult
from src.workflow.models.workflow_state import FeatIssueWorkflowState


class FindRelevantBcStep:

    async def execute(self, state: FeatIssueWorkflowState) -> StepResult:
        agent = AgentExecutor.build(AgentKey.RELEVANT_BC_FINDER)
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
