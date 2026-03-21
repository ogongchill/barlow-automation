"""SQS 기반 IQueueSender 구현체."""

import json
import logging

import boto3

from src.config import config
from src.domain.queue import IQueueSender

logger = logging.getLogger(__name__)


class SqsQueueSender(IQueueSender):
    """boto3 SQS 클라이언트 기반 IQueueSender."""

    def __init__(self) -> None:
        self._client = boto3.client("sqs")

    def send(self, message: dict) -> None:
        self._client.send_message(
            QueueUrl=config.sqs_queue_url,
            MessageBody=json.dumps(message, ensure_ascii=False),
        )
        logger.debug("sqs | sent type=%s", message.get("type"))
