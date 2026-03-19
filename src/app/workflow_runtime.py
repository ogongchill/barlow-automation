"""workflow_runtime -- WorkflowInstance 생성·재개·step 실행을 조율하는 핵심 오케스트레이터."""

import logging
import uuid

from slack_sdk.web.async_client import AsyncWebClient

from src.domain.common.models.workflow_instance import IWorkflowInstanceRepository
from src.domain.common.models.lifecycle import WorkflowStatus
from src.domain.common.models.workflow_instance import WorkflowInstance

# feature definitions
import src.domain.feat.definition as _feat_def
import src.domain.refactor.definition as _refactor_def
import src.domain.fix.definition as _fix_def

# feat steps
from src.domain.feat.steps.create_github_issue import CreateGithubIssueStep
from src.domain.feat.steps.find_relevant_bc import FindRelevantBcStep
from src.domain.feat.steps.generate_issue_draft import GenerateIssueDraftStep
from src.domain.feat.steps.regenerate_issue_draft import RegenerateIssueDraftStep
from src.domain.feat.steps.wait_confirmation import WaitConfirmationStep

# state registration (side effect import)
import src.domain.feat.models.state  # noqa: F401

logger = logging.getLogger(__name__)

_DEFINITIONS = {
    "feat_issue":     _feat_def,
    "refactor_issue": _refactor_def,
    "fix_issue":      _fix_def,
}


def _subcommand_from(workflow_type: str) -> str:
    """workflow_type에서 subcommand를 추출한다. e.g. 'feat_issue' -> 'feat'"""
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
        defn = _DEFINITIONS.get(workflow_type)
        first_step = defn.FIRST_STEP if defn else "find_relevant_bc"
        instance = WorkflowInstance.create(
            workflow_type=workflow_type,
            slack_channel_id=slack_channel_id,
            slack_user_id=slack_user_id,
            user_message=user_message,
            first_step=first_step,
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

        defn = _DEFINITIONS.get(instance.workflow_type)
        resume_map = defn.RESUME_MAP if defn else {}
        next_step = resume_map.get(action)
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
        defn = _DEFINITIONS.get(instance.workflow_type)
        graph = defn.GRAPH if defn else {}

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
                        text=f"GitHub 이슈가 생성되었습니다: {issue_url}",
                        blocks=[],
                    )
                else:
                    await self._slack_client.chat_postMessage(
                        channel=instance.slack_channel_id,
                        text=f"GitHub 이슈가 생성되었습니다: {issue_url}",
                    )
                await self._repo.save(instance)
                logger.info(
                    "step | completed workflow_id=%s issue_url=%s",
                    instance.workflow_id,
                    issue_url,
                )
                break

            else:  # continue
                node = graph.get(step_name)
                next_step = result.next_step or (node.on_continue if node else None)
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
        if step_name == "wait_confirmation":
            return WaitConfirmationStep(
                subcommand=subcommand,
                workflow_id=instance.workflow_id,
                user_id=instance.slack_user_id,
            )
        if step_name == "regenerate_issue_draft":
            return RegenerateIssueDraftStep(subcommand)
        if step_name == "create_github_issue":
            return CreateGithubIssueStep(subcommand)
        raise ValueError(f"Unknown step name: {step_name}")
