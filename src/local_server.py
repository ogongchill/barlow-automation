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
import src.lambda_worker as worker  # noqa: E402
from src.config import config
from src.controller.app import create_app
from src.controller.handler import slash
from src.controller.router import register
from src.logging_config import setup_logging
from src.storage.local_queue_sender import LocalQueueSender
from src.storage.memory_idempotency_repository import MemoryIdempotencyRepository
from src.storage.memory_pending_repository import MemoryPendingRepository

setup_logging()
logger = logging.getLogger(__name__)


def _build_app():
    """인메모리 의존성을 주입하고 Bolt AsyncApp을 반환한다."""
    pending_repo = MemoryPendingRepository()
    idempotency_repo = MemoryIdempotencyRepository()

    # Worker 의존성 주입 (도메인 로직 공유)
    worker._pending_repo = pending_repo
    worker._idempotency_repo = idempotency_repo

    # Ack 핸들러 의존성 주입
    slash.configure(
        pending_repo=pending_repo,
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
