"""wait_issue_decision -- relevant issue 분석 결과 전달 후 사용자 결정 대기."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WaitIssueDecisionInput:
    relevant_issues: str  # JSON
    workflow_id: str
    user_id: str


@dataclass(frozen=True)
class WaitIssueDecisionOutput:
    blocks: list


class WaitIssueDecisionStep:

    async def execute(
        self, input: WaitIssueDecisionInput
    ) -> WaitIssueDecisionOutput:
        from src.app.slack.payload_mapper import build_issue_decision_blocks

        blocks = build_issue_decision_blocks(
            user=input.user_id,
            relevant_issues_json=input.relevant_issues,
            workflow_id=input.workflow_id,
        )
        return WaitIssueDecisionOutput(blocks=blocks)
