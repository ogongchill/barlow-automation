"""로컬 개발용 IQueueSender — lambda_worker._process()를 직접 호출한다."""

import asyncio
import json
import logging

from src.domain.queue import IQueueSender

logger = logging.getLogger(__name__)


class LocalQueueSender(IQueueSender):
    """SQS 없이 lambda_worker._process()를 asyncio 백그라운드 태스크로 실행한다."""

    def send(self, message: dict) -> None:
        import src.lambda_worker as worker

        body = json.dumps(message, ensure_ascii=False)
        asyncio.create_task(worker._process(body))
        logger.debug("local_queue | scheduled type=%s", message.get("type"))
