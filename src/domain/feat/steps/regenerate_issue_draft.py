"""regenerate_issue_draft -- FEAT_REISSUE_GEN agent execution."""

from src.domain.feat.executor import FeatAgentExecutor, FeatAgentKey
from src.domain.common.models.step_result import StepResult
from src.domain.feat.models.state import FeatIssueWorkflowState


class RegenerateIssueDraftStep:

    def __init__(self, subcommand: str) -> None:
        self._subcommand = subcommand

    def _build_prompt(self, state: FeatIssueWorkflowState) -> str:
        parts: list[str] = []
        if state.bc_candidates:
            parts.append(f"[BC Finder Context]\n{state.bc_candidates}")
        if state.issue_draft:
            parts.append(f"[Current Issue Draft]\n{state.issue_draft}")
        if state.user_feedback:
            parts.append(f"Additional requirements: {state.user_feedback}")
        return "\n\n".join(parts)

    async def execute(self, state: FeatIssueWorkflowState) -> StepResult:
        agent = FeatAgentExecutor.build(FeatAgentKey.ISSUE_REGEN)
        prompt = self._build_prompt(state)
        result = await agent.run(prompt)
        issue_draft_json = (
            result.typed_output.model_dump_json()
            if result.typed_output
            else result.output
        )
        return StepResult(
            status="success",
            control_signal="continue",
            state_patch={"issue_draft": issue_draft_json},
        )
