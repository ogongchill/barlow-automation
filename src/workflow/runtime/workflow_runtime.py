"""workflow_runtime -- WorkflowInstance 생성·재개·step 실행을 조율하는 핵심 오케스트레이터."""

import logging
import uuid

from slack_sdk.web.async_client import AsyncWebClient

from src.infrastructure.storage.dynamodb.workflow_instance_store import IWorkflowInstanceRepository
from src.workflow.models.lifecycle import WorkflowStatus
from src.workflow.models.workflow_instance import WorkflowInstance
from src.workflow.steps.feat_issue.create_github_issue_step import CreateGithubIssueStep
from src.workflow.steps.feat_issue.find_relevant_bc_step import FindRelevantBcStep
from src.workflow.steps.feat_issue.generate_issue_draft_step import GenerateIssueDraftStep
from src.workflow.steps.feat_issue.regenerate_issue_draft_step import RegenerateIssueDraftStep
from src.workflow.steps.common.wait_issue_confirmation_step import WaitIssueDraftConfirmationStep

logger = logging.getLogger(__name__)

# step name → next step name (control_signal="continue" 일 때)
_NEXT_STEP: dict[str, str] = {
    "find_relevant_bc": "generate_issue_draft",
    "generate_issue_draft": "wait_issue_confirmation",
    "regenerate_issue_draft": "wait_issue_confirmation",
}

# resume action → next step name
_RESUME_STEP: dict[str, str] = {
    "accept": "create_github_issue",
    "reject": "regenerate_issue_draft",
    "drop_restart": "regenerate_issue_draft",
}


def _subcommand_from(workflow_type: str) -> str:
    """workflow_type에서 subcommand를 추출한다. e.g. 'feat_issue' → 'feat'"""
    return workflow_type.replace("_issue", "")


class WorkflowRuntime:
    """step 실행, state 로드/저장, Slack 메시징을 조율한다."""

    def __init__(
        self,
        repo: IWorkflowInstanceRepository,
        slack_client: AsyncWebClient,
    ) -> None:
        self._repo = repo
        self._slack_client = slack_client

    async def start(
        self,
        workflow_type: str,
        slack_channel_id: str,
        slack_user_id: str,
        user_message: str,
    ) -> WorkflowInstance:
        """새 WorkflowInstance를 생성하고 첫 step부터 실행한다."""
        instance = WorkflowInstance.create(
            workflow_type=workflow_type,
            slack_channel_id=slack_channel_id,
            slack_user_id=slack_user_id,
            user_message=user_message,
            first_step="find_relevant_bc",
        )
        instance.status = WorkflowStatus.RUNNING
        await self._repo.save(instance)
        await self._execute_until_wait(instance)
        return instance

    async def resume(
        self,
        workflow_id: str,
        action: str,
        feedback: str | None = None,
        dropped_ids: list[str] | None = None,
    ) -> WorkflowInstance | None:
        """기존 WorkflowInstance를 재개하고 사용자 액션에 따라 실행한다."""
        instance = await self._repo.get(workflow_id)
        if not instance:
            logger.warning("resume | workflow not found workflow_id=%s", workflow_id)
            return None

        if feedback:
            instance.state.user_feedback = feedback
        if dropped_ids:
            instance.state.dropped_item_ids = dropped_ids

        next_step = _RESUME_STEP.get(action)
        if not next_step:
            logger.warning("resume | unknown action=%s", action)
            return instance

        instance.current_step = next_step
        instance.status = WorkflowStatus.RUNNING
        instance.pending_action_token = None
        await self._repo.save(instance)
        await self._execute_until_wait(instance)
        return instance

    async def _execute_until_wait(self, instance: WorkflowInstance) -> None:
        """WAITING 또는 COMPLETED 상태에 도달할 때까지 step을 순차 실행한다."""
        subcommand = _subcommand_from(instance.workflow_type)

        while True:
            step_name = instance.current_step
            logger.info(
                "step | executing workflow_id=%s step=%s",
                instance.workflow_id,
                step_name,
            )

            step = self._build_step(step_name, subcommand, instance)
            result = await step.execute(instance.state)
            instance.state.apply_patch(result.state_patch)

            if result.control_signal == "wait_for_user":
                blocks = (result.user_action_request or {}).get("blocks", [])
                response = await self._slack_client.chat_postMessage(
                    channel=instance.slack_channel_id,
                    blocks=blocks,
                )
                instance.slack_message_ts = response["ts"]
                instance.status = WorkflowStatus.WAITING
                instance.pending_action_token = str(uuid.uuid4())
                await self._repo.save(instance)
                logger.info(
                    "step | waiting workflow_id=%s step=%s",
                    instance.workflow_id,
                    step_name,
                )
                break

            elif result.control_signal == "stop":
                instance.status = WorkflowStatus.COMPLETED
                issue_url = instance.state.github_issue_url or ""
                if instance.slack_message_ts:
                    await self._slack_client.chat_update(
                        channel=instance.slack_channel_id,
                        ts=instance.slack_message_ts,
                        text=f"✅ GitHub 이슈가 생성되었습니다: {issue_url}",
                        blocks=[],
                    )
                else:
                    await self._slack_client.chat_postMessage(
                        channel=instance.slack_channel_id,
                        text=f"✅ GitHub 이슈가 생성되었습니다: {issue_url}",
                    )
                await self._repo.save(instance)
                logger.info(
                    "step | completed workflow_id=%s issue_url=%s",
                    instance.workflow_id,
                    issue_url,
                )
                break

            else:  # continue
                next_step = result.next_step or _NEXT_STEP.get(step_name)
                if not next_step:
                    logger.error(
                        "step | no next step defined for step=%s", step_name
                    )
                    instance.status = WorkflowStatus.FAILED
                    await self._repo.save(instance)
                    break
                instance.current_step = next_step
                await self._repo.save(instance)

    def _build_step(self, step_name: str, subcommand: str, instance: WorkflowInstance):
        """step 이름에 해당하는 step 인스턴스를 반환한다."""
        if step_name == "find_relevant_bc":
            return FindRelevantBcStep()
        if step_name == "generate_issue_draft":
            return GenerateIssueDraftStep(subcommand)
        if step_name == "wait_issue_confirmation":
            return WaitIssueDraftConfirmationStep(
                subcommand=subcommand,
                workflow_id=instance.workflow_id,
                user_id=instance.slack_user_id,
            )
        if step_name == "regenerate_issue_draft":
            return RegenerateIssueDraftStep(subcommand)
        if step_name == "create_github_issue":
            return CreateGithubIssueStep(subcommand)
        raise ValueError(f"Unknown step name: {step_name}")
