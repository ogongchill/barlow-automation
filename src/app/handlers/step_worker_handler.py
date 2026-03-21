"""step_worker_handler -- SQS 이벤트를 받아 WorkflowRuntime을 통해 파이프라인을 실행한다."""

import asyncio
import json
import logging

from slack_sdk.web.async_client import AsyncWebClient

from src.agent.mcp import GitHubMCPFactory
from src.config import config
from src.domain.common.ports.active_session import IActiveSessionRepository
from src.domain.common.ports.idempotency import IIdempotencyRepository
from src.infrastructure.storage.dynamodb.active_session_store import (
    DynamoActiveSessionStore,
)
from src.infrastructure.storage.dynamodb.pending_action_store import (
    DynamoPendingActionStore,
)
from src.infrastructure.storage.dynamodb.workflow_instance_store import (
    DynamoWorkflowInstanceStore,
    IWorkflowInstanceRepository,
)
from src.logging_config import setup_logging
from src.app.workflow_runtime import WorkflowRuntime

setup_logging()
logger = logging.getLogger(__name__)

_workflow_repo: IWorkflowInstanceRepository = DynamoWorkflowInstanceStore()
_idempotency_repo: IIdempotencyRepository = DynamoPendingActionStore()
_active_session_repo: IActiveSessionRepository = DynamoActiveSessionStore()


def configure(
    workflow_repo: IWorkflowInstanceRepository,
    idempotency_repo: IIdempotencyRepository,
    active_session_repo: IActiveSessionRepository,
) -> None:
    """진입점(로컬 서버)에서 의존성을 주입한다. Lambda는 호출하지 않는다."""
    global _workflow_repo, _idempotency_repo, _active_session_repo
    _workflow_repo = workflow_repo
    _idempotency_repo = idempotency_repo
    _active_session_repo = active_session_repo


async def _process(body: str) -> None:
    event = json.loads(body)
    event_type = event.get("type")
    dedup_id = event.get("dedup_id", "")

    if dedup_id and not await _idempotency_repo.try_acquire(dedup_id):
        logger.info("duplicate event skipped dedup_id=%s", dedup_id)
        return

    client = AsyncWebClient(token=config.slack_bot_token)
    runtime = WorkflowRuntime(
        repo=_workflow_repo,
        slack_client=client,
        active_session_repo=_active_session_repo,
    )

    channel_id = event.get("channel_id", "")
    try:
        if event_type == "pipeline_start":
            subcommand = event["subcommand"]
            workflow_type = f"{subcommand}_issue"
            await runtime.start(
                workflow_type=workflow_type,
                slack_channel_id=event["channel_id"],
                slack_user_id=event["user_id"],
                user_message=event["user_message"],
            )
        elif event_type in (
            "accept", "reject", "drop_restart",
            "reject_duplicate", "extend_existing",
            "block_existing", "create_new_independent",
        ):
            workflow_id = event.get("workflow_id")
            if not workflow_id:
                logger.error(
                    "resume | missing workflow_id in event type=%s", event_type
                )
                return
            feedback = (
                event.get("additional_requirements") or event.get("feedback")
            )
            dropped_ids = event.get("dropped_ids")
            instance = await runtime.resume(
                workflow_id=workflow_id,
                action=event_type,
                feedback=feedback,
                dropped_ids=dropped_ids,
            )
            if instance and not channel_id:
                channel_id = instance.slack_channel_id
        else:
            logger.warning("unknown SQS message type: %s", event_type)

        if dedup_id:
            await _idempotency_repo.mark_done(dedup_id)

    except Exception as e:
        logger.error(
            "pipeline failed type=%s error=%s", event_type, e, exc_info=True
        )
        if not channel_id and event_type in ("reject", "drop_restart", "accept"):
            workflow_id = event.get("workflow_id", "")
            if workflow_id:
                instance = await _workflow_repo.get(workflow_id)
                if instance:
                    channel_id = instance.slack_channel_id
        if channel_id:
            await client.chat_postMessage(
                channel=channel_id,
                text="⚠️ 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            )
    finally:
        await GitHubMCPFactory.disconnect()


def handler(event, context) -> None:
    """AWS Lambda entry point -- SQS trigger."""
    async def _run():
        for record in event.get("Records", []):
            await _process(record["body"])

    asyncio.run(_run())
