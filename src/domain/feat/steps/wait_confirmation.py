"""wait_confirmation -- issue draft Slack 전송 후 사용자 응답 대기."""

from src.domain.feat.models.issue import FeatTemplate
from src.domain.common.models.step_result import StepResult
from src.domain.feat.models.state import FeatIssueWorkflowState


class WaitConfirmationStep:
    """issue_draft를 Slack 블록으로 변환하고 사용자 응답을 대기한다."""

    def __init__(self, subcommand: str, workflow_id: str, user_id: str) -> None:
        self._subcommand = subcommand
        self._workflow_id = workflow_id
        self._user_id = user_id

    async def execute(self, state: FeatIssueWorkflowState) -> StepResult:
        from src.app.slack.payload_mapper import build_issue_blocks

        template = FeatTemplate.model_validate_json(state.issue_draft)
        blocks = build_issue_blocks(
            user=self._user_id,
            template=template,
            usage_text="",
            workflow_id=self._workflow_id,
        )
        return StepResult(
            status="waiting",
            control_signal="wait_for_user",
            user_action_request={"blocks": blocks},
        )
