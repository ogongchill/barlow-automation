"""regenerate_issue_draft -- ISSUE_REGEN agent execution."""

from dataclasses import dataclass

from src.domain.feat.executor import FeatAgentExecutor, FeatAgentKey


@dataclass(frozen=True)
class RegenerateIssueDraftInput:
    bc_candidates: str | None
    issue_draft: str | None
    user_feedback: str | None


@dataclass(frozen=True)
class RegenerateIssueDraftOutput:
    issue_draft: str


class RegenerateIssueDraftStep:

    async def execute(
        self, input: RegenerateIssueDraftInput
    ) -> RegenerateIssueDraftOutput:
        agent = FeatAgentExecutor.build(FeatAgentKey.ISSUE_REGEN)
        parts: list[str] = []
        if input.bc_candidates:
            parts.append(f"[BC Finder Context]\n{input.bc_candidates}")
        if input.issue_draft:
            parts.append(f"[Current Issue Draft]\n{input.issue_draft}")
        if input.user_feedback:
            parts.append(f"Additional requirements: {input.user_feedback}")
        result = await agent.run("\n\n".join(parts))
        issue_draft_json = (
            result.typed_output.model_dump_json()
            if result.typed_output
            else result.output
        )
        return RegenerateIssueDraftOutput(issue_draft=issue_draft_json)
