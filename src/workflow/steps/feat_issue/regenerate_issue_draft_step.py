"""regenerate_issue_draft_step -- FEAT/REFACTOR/FIX_REISSUE_GEN agent execution."""

from src.workflow.executors.agent_executor import AgentExecutor, AgentKey
from src.workflow.models.step_result import StepResult
from src.workflow.models.workflow_state import FeatIssueWorkflowState

_SUBCOMMAND_KEY = {
    "feat": AgentKey.FEAT_REISSUE_GEN,
    "refactor": AgentKey.REFACTOR_REISSUE_GEN,
    "fix": AgentKey.FIX_REISSUE_GEN,
}


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
        key = _SUBCOMMAND_KEY.get(self._subcommand)
        if not key:
            raise ValueError(f"Unknown subcommand: {self._subcommand}")
        agent = AgentExecutor.build(key)
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
