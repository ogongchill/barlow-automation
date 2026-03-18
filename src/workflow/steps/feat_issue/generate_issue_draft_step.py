"""generate_issue_draft_step -- FEAT/REFACTOR/FIX_ISSUE_GEN agent execution."""

from src.workflow.executors.agent_executor import AgentExecutor, AgentKey
from src.workflow.models.step_result import StepResult
from src.workflow.models.workflow_state import FeatIssueWorkflowState

_SUBCOMMAND_KEY = {
    "feat": AgentKey.FEAT_ISSUE_GEN,
    "refactor": AgentKey.REFACTOR_ISSUE_GEN,
    "fix": AgentKey.FIX_ISSUE_GEN,
}


class GenerateIssueDraftStep:

    def __init__(self, subcommand: str) -> None:
        self._subcommand = subcommand

    def _build_prompt(self, state: FeatIssueWorkflowState) -> str:
        parts: list[str] = []
        if state.bc_candidates:
            parts.append(f"[BC Finder Candidates]\n{state.bc_candidates}")
        if state.bc_decision:
            parts.append(f"[BC Decision]\n{state.bc_decision}")
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
            internal_trace={
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
            },
        )
