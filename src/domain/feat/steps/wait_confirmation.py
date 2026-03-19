"""wait_confirmation -- issue draft Slack 전송 후 사용자 응답 대기."""

from dataclasses import dataclass

from src.domain.feat.models.issue import FeatTemplate


@dataclass(frozen=True)
class WaitConfirmationInput:
    issue_draft: str
    workflow_id: str
    user_id: str


@dataclass(frozen=True)
class WaitConfirmationOutput:
    blocks: list


class WaitConfirmationStep:

    async def execute(
        self, input: WaitConfirmationInput
    ) -> WaitConfirmationOutput:
        from src.app.slack.payload_mapper import build_issue_blocks

        template = FeatTemplate.model_validate_json(input.issue_draft)
        blocks = build_issue_blocks(
            user=input.user_id,
            template=template,
            usage_text="",
            workflow_id=input.workflow_id,
        )
        return WaitConfirmationOutput(blocks=blocks)
