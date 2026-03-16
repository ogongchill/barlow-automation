"""barlow-idempotency DynamoDB 테이블 — IIdempotencyRepository 구현체."""

import asyncio
import logging
import time
from functools import partial

import boto3
from botocore.exceptions import ClientError

from src.domain.idempotency import IIdempotencyRepository
from src.storage.models import IDEMPOTENCY_TTL_SECONDS

logger = logging.getLogger(__name__)

TABLE_NAME = "barlow-idempotency"

_STATUS_PROCESSING = "PROCESSING"
_STATUS_DONE = "DONE"


async def _run(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))


class DynamoIdempotencyRepository(IIdempotencyRepository):
    """barlow-idempotency DynamoDB 테이블 기반 IIdempotencyRepository 구현체."""

    def __init__(self) -> None:
        self._table = boto3.resource("dynamodb").Table(TABLE_NAME)

    async def try_acquire(self, message_ts: str) -> bool:
        try:
            await _run(
                self._table.put_item,
                Item={
                    "pk": message_ts,
                    "status": _STATUS_PROCESSING,
                    "ttl": int(time.time()) + IDEMPOTENCY_TTL_SECONDS,
                },
                ConditionExpression="attribute_not_exists(pk)",
            )
            logger.debug("idempotency | acquired pk=%s", message_ts)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning("idempotency | duplicate detected pk=%s", message_ts)
                return False
            raise

    async def mark_done(self, message_ts: str) -> None:
        await _run(
            self._table.update_item,
            Key={"pk": message_ts},
            UpdateExpression="SET #s = :done",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":done": _STATUS_DONE},
        )
        logger.debug("idempotency | marked done pk=%s", message_ts)
