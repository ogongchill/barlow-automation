"""workflow_runtime -- WorkflowInstance 생성·재개·step 실행 오케스트레이터."""

import logging
import uuid

from slack_sdk.web.async_client import AsyncWebClient

from src.domain.common.models.lifecycle import WorkflowStatus
from src.domain.common.models.step_result import ControlSignal
from src.domain.common.models.workflow_instance import (
    IWorkflowInstanceRepository,
    WorkflowInstance,
)
from src.domain.common.ports.active_session import IActiveSessionRepository
from src.domain.feat.models.issue_decision import Decision

import src.domain.feat.definition as _feat_def
import src.domain.refactor.definition as _refactor_def
import src.domain.fix.definition as _fix_def

# state registration (side effect import)
import src.domain.feat.models.state  # noqa: F401

logger = logging.getLogger(__name__)

_DEFINITIONS = {
    "feat_issue":     _feat_def,
    "refactor_issue": _refactor_def,
    "fix_issue":      _fix_def,
}


class WorkflowRuntime:
    """step 실행, state 로드/저장, Slack 메시징을 조율한다."""

    def __init__(
        self,
        repo: IWorkflowInstanceRepository,
        slack_client: AsyncWebClient,
        active_session_repo: IActiveSessionRepository,
    ) -> None:
        self._repo = repo
        self._slack_client = slack_client
        self._active_session_repo = active_session_repo

    async def start(
        self,
        workflow_type: str,
        slack_channel_id: str,
        slack_user_id: str,
        user_message: str,
    ) -> WorkflowInstance | None:
        """새 WorkflowInstance를 생성하고 첫 step부터 실행한다."""
        existing_id = await self._active_session_repo.get_workflow_id(
            slack_channel_id, slack_user_id
        )
        if existing_id:
            logger.warning(
                "start | active workflow exists channel=%s user=%s workflow_id=%s",
                slack_channel_id, slack_user_id, existing_id,
            )
            await self._slack_client.chat_postMessage(
                channel=slack_channel_id,
                text=(
                    "이미 진행 중인 워크플로우가 있습니다. "
                    "`/drop` 으로 중단 후 다시 시도해 주세요."
                ),
            )
            return None

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
        await self._active_session_repo.set(
            slack_channel_id, slack_user_id, instance.workflow_id
        )
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
            logger.warning(
                "resume | workflow not found workflow_id=%s", workflow_id
            )
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

        try:
            instance.state.apply_patch({"issue_decision": Decision(action)})
        except ValueError:
            pass  # accept, reject, drop_restart 등 Decision이 아닌 액션
        instance.current_step = next_step
        instance.status = WorkflowStatus.RUNNING
        instance.pending_action_token = None
        await self._repo.save(instance)
        await self._execute_until_wait(instance)
        return instance

    async def _execute_until_wait(self, instance: WorkflowInstance) -> None:
        """WAITING 또는 COMPLETED 상태에 도달할 때까지 step을 순차 실행한다."""
        defn = _DEFINITIONS.get(instance.workflow_type)
        graph = defn.GRAPH if defn else {}

        while True:
            step_name = instance.current_step
            node = graph.get(step_name)
            if not node:
                logger.error("step | unknown step=%s", step_name)
                instance.status = WorkflowStatus.FAILED
                await self._repo.save(instance)
                await self._active_session_repo.clear(
                    instance.slack_channel_id, instance.slack_user_id
                )
                break

            logger.info(
                "step | executing workflow_id=%s step=%s",
                instance.workflow_id,
                step_name,
            )

            input = node.extract_input(instance)
            output = await node.step.execute(input)
            node.apply_output(instance.state, output)

            if node.control_signal == ControlSignal.WAIT_FOR_USER:
                user_action = (
                    node.extract_user_action(output)
                    if node.extract_user_action
                    else {}
                )
                blocks = user_action.get("blocks", [])
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

            elif node.control_signal == ControlSignal.STOP:
                instance.status = WorkflowStatus.COMPLETED
                message = (
                    instance.state.completion_message
                    or (
                        f"GitHub 이슈가 생성되었습니다: {instance.state.github_issue_url}"
                        if instance.state.github_issue_url
                        else "워크플로우가 완료되었습니다."
                    )
                )
                if instance.slack_message_ts:
                    await self._slack_client.chat_update(
                        channel=instance.slack_channel_id,
                        ts=instance.slack_message_ts,
                        text=message,
                        blocks=[],
                    )
                else:
                    await self._slack_client.chat_postMessage(
                        channel=instance.slack_channel_id,
                        text=message,
                    )
                await self._repo.save(instance)
                await self._active_session_repo.clear(
                    instance.slack_channel_id, instance.slack_user_id
                )
                logger.info(
                    "step | completed workflow_id=%s",
                    instance.workflow_id,
                )
                break

            else:  # CONTINUE
                next_step = node.on_continue
                if not next_step:
                    logger.error(
                        "step | no next step defined for step=%s", step_name
                    )
                    instance.status = WorkflowStatus.FAILED
                    await self._repo.save(instance)
                    await self._active_session_repo.clear(
                        instance.slack_channel_id, instance.slack_user_id
                    )
                    break
                instance.current_step = next_step
                await self._repo.save(instance)
