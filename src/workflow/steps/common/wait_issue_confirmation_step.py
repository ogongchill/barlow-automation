"""wait_issue_confirmation_step -- issue draft Slack 전송 후 사용자 응답 대기."""

from src.domain.issue.entities import BaseIssueTemplate, FeatTemplate, RefactorTemplate, FixTemplate
from src.workflow.mappers.slack_payload_mapper import build_issue_blocks
from src.workflow.models.step_result import StepResult
from src.workflow.models.workflow_state import FeatIssueWorkflowState

_TEMPLATE_CLS: dict[str, type[BaseIssueTemplate]] = {
    "feat": FeatTemplate,
    "refactor": RefactorTemplate,
    "fix": FixTemplate,
}


class WaitIssueDraftConfirmationStep:
    """issue_draft를 Slack 블록으로 변환하고 사용자 응답을 대기한다."""

    def __init__(self, subcommand: str, workflow_id: str, user_id: str) -> None:
        self._subcommand = subcommand
        self._workflow_id = workflow_id
        self._user_id = user_id

    async def execute(self, state: FeatIssueWorkflowState) -> StepResult:
        template_cls = _TEMPLATE_CLS.get(self._subcommand, FeatTemplate)
        template = template_cls.model_validate_json(state.issue_draft)
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
