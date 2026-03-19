"""generate_issue_draft -- ISSUE_GEN agent execution."""

from dataclasses import dataclass

from src.domain.feat.executor import FeatAgentExecutor, FeatAgentKey


@dataclass(frozen=True)
class GenerateIssueDraftInput:
    bc_candidates: str | None
    bc_decision: str | None


@dataclass(frozen=True)
class GenerateIssueDraftOutput:
    issue_draft: str
    internal_trace: dict | None = None


class GenerateIssueDraftStep:

    async def execute(
        self, input: GenerateIssueDraftInput
    ) -> GenerateIssueDraftOutput:
        agent = FeatAgentExecutor.build(FeatAgentKey.ISSUE_GEN)
        parts: list[str] = []
        if input.bc_candidates:
            parts.append(f"[BC Finder Candidates]\n{input.bc_candidates}")
        if input.bc_decision:
            parts.append(f"[BC Decision]\n{input.bc_decision}")
        result = await agent.run("\n\n".join(parts))
        issue_draft_json = (
            result.typed_output.model_dump_json()
            if result.typed_output
            else result.output
        )
        return GenerateIssueDraftOutput(
            issue_draft=issue_draft_json,
            internal_trace={
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
            },
        )
