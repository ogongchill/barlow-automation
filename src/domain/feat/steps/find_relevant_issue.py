"""find_relevant_issue -- RELEVANT_ISSUE_FINDER agent execution."""

from dataclasses import dataclass

from src.domain.feat.executor import FeatAgentExecutor, FeatAgentKey


@dataclass(frozen=True)
class FindRelevantIssueInput:
    user_message: str
    bc_candidates: str | None


@dataclass(frozen=True)
class FindRelevantIssueOutput:
    relevant_issues: str  # JSON string of RelevantIssue
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
        relevant_issues_json = (
            result.typed_output.model_dump_json()
            if result.typed_output
            else result.output
        )
        return FindRelevantIssueOutput(
            relevant_issues=relevant_issues_json,
            internal_trace={
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
            },
        )
