"""generate_issue_draft -- FEAT/REFACTOR/FIX_ISSUE_GEN agent execution."""

from src.domain.feat.executor import FeatAgentExecutor, FeatAgentKey
from src.domain.common.models.step_result import StepResult
from src.domain.feat.models.state import FeatIssueWorkflowState


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
        agent = FeatAgentExecutor.build(FeatAgentKey.ISSUE_GEN)
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
