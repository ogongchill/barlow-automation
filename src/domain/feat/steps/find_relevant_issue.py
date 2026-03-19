"""find_relevant_issue -- RELEVANT_ISSUE_FINDER agent execution."""

from dataclasses import dataclass

from src.domain.feat.agents.relevant_issue_finder.schema import RelevantIssue
from src.domain.feat.executor import FeatAgentExecutor, FeatAgentKey


@dataclass(frozen=True)
class FindRelevantIssueInput:
    user_message: str
    bc_candidates: str | None


@dataclass(frozen=True)
class FindRelevantIssueOutput:
    relevant_issues: RelevantIssue
    internal_trace: dict | None = None


class FindRelevantIssueStep:

    async def execute(
        self, input: FindRelevantIssueInput
    ) -> FindRelevantIssueOutput:
        agent = await FeatAgentExecutor.build(
            FeatAgentKey.RELEVANT_ISSUE_FINDER
        )
        prompt = input.user_message
        if input.bc_candidates:
            prompt = f"[BC Context]\n{input.bc_candidates}\n\n{input.user_message}"
        result = await agent.run(prompt)
        relevant_issues = (
            result.typed_output
            if result.typed_output
            else RelevantIssue.model_validate_json(result.output)
        )
        return FindRelevantIssueOutput(
            relevant_issues=relevant_issues,
            internal_trace={
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
            },
        )
