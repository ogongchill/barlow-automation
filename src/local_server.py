"""로컬 개발 서버 — Socket Mode + 인메모리 저장소."""

import asyncio
import json
import logging

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from src.config import config
from src.controller.handler import slash
from src.controller.router import register
from src.domain.queue import IQueueSender
from src.app.handlers.step_worker_handler import _process, configure as configure_worker
from src.infrastructure.storage.memory.active_session_store import (
    MemoryActiveSessionStore,
)
from src.infrastructure.storage.memory.pending_action_store import (
    MemoryPendingActionStore,
)
from src.infrastructure.storage.memory.workflow_instance_store import (
    MemoryWorkflowInstanceStore,
)
from src.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class _InMemoryQueue(IQueueSender):
    """SQS 대신 _process를 직접 호출하는 인메모리 큐."""

    def send(self, message: dict) -> None:
        body = json.dumps(message)
        asyncio.create_task(_process(body))


_workflow_repo = MemoryWorkflowInstanceStore()
_idempotency_repo = MemoryPendingActionStore()
_active_session_repo = MemoryActiveSessionStore()

configure_worker(
    workflow_repo=_workflow_repo,
    idempotency_repo=_idempotency_repo,
    active_session_repo=_active_session_repo,
)
slash.configure(
    workflow_repo=_workflow_repo,
    active_session_repo=_active_session_repo,
    queue=_InMemoryQueue(),
)

app = AsyncApp(
    token=config.slack_bot_token,
    signing_secret=config.slack_signing_secret,
)
register(app)


async def main() -> None:
    handler = AsyncSocketModeHandler(app, config.slack_app_token)
    logger.info("로컬 서버 시작 (Socket Mode)")
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
