"""로컬 개발 서버 — Socket Mode + 인메모리 저장소.

에이전트 프롬프트 및 도메인 로직 테스트용.
ngrok 없이 실행 가능하며, 도메인 로직은 Lambda Worker와 동일하게 재사용한다.

실행:
    python src/local_server.py
    (.env에 SLACK_APP_TOKEN=xapp-... 필요)
"""

import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "default.env")

import os  # noqa: E402
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-northeast-2")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "local")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "local")

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler  # noqa: E402
import src.app.handlers.step_worker_handler as worker  # noqa: E402
from src.config import config  # noqa: E402
from src.controller.app import create_app  # noqa: E402
from src.controller.handler import slash  # noqa: E402
from src.controller.router import register  # noqa: E402
from src.infrastructure.storage.memory.pending_action_store import (  # noqa: E402
    MemoryPendingActionStore,
)
from src.infrastructure.storage.memory.workflow_instance_store import (  # noqa: E402
    MemoryWorkflowInstanceStore,
)
from src.logging_config import setup_logging  # noqa: E402

setup_logging()
logger = logging.getLogger(__name__)


class LocalQueueSender:
    """SQS 없이 step_worker_handler._process()를 asyncio 태스크로 실행한다."""

    def send(self, message: dict) -> None:
        import json
        body = json.dumps(message, ensure_ascii=False)
        asyncio.create_task(worker._process(body))
        logger.debug("local_queue | scheduled type=%s", message.get("type"))


def _build_app():
    """인메모리 의존성을 주입하고 Bolt AsyncApp을 반환한다."""
    workflow_repo = MemoryWorkflowInstanceStore()
    idempotency_repo = MemoryPendingActionStore()

    # Worker 의존성 주입 (도메인 로직 공유)
    worker._workflow_repo = workflow_repo
    worker._idempotency_repo = idempotency_repo

    # Ack 핸들러 의존성 주입
    slash.configure(
        workflow_repo=workflow_repo,
        queue=LocalQueueSender(),
    )

    app = create_app()
    register(app)
    return app


async def main() -> None:
    if not config.slack_app_token:
        raise EnvironmentError(
            "SLACK_APP_TOKEN이 설정되지 않았습니다. "
            ".env에 SLACK_APP_TOKEN=xapp-... 를 추가하세요."
        )

    app = _build_app()
    handler = AsyncSocketModeHandler(app, config.slack_app_token)
    logger.info("Socket Mode 로컬 서버 시작")
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
