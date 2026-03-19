"""Pending Action DynamoDB 저장소 -- 멱등성 보장용."""

import asyncio
import logging
import os
import time
from functools import partial

import boto3
from botocore.exceptions import ClientError

from src.domain.common.ports.idempotency import IIdempotencyRepository

logger = logging.getLogger(__name__)

TABLE_NAME = os.environ.get("PENDING_ACTION_TABLE_NAME", "barlow-pending-action")
PENDING_ACTION_TTL_SECONDS = 60 * 60  # 1시간


async def _run(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))


class DynamoPendingActionStore(IIdempotencyRepository):
    """barlow-pending-action DynamoDB 테이블 기반 멱등성 저장소."""

    def __init__(self, table_name: str | None = None) -> None:
        self._table_name = table_name or TABLE_NAME
        self._table = boto3.resource("dynamodb", region_name="ap-northeast-2").Table(self._table_name)

    async def try_acquire(self, key: str) -> bool:
        try:
            await _run(
                self._table.put_item,
                Item={
                    "pk": key,
                    "status": "PROCESSING",
                    "ttl": int(time.time()) + PENDING_ACTION_TTL_SECONDS,
                },
                ConditionExpression="attribute_not_exists(pk)",
            )
            logger.debug("pending_action | acquired pk=%s", key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning("pending_action | duplicate detected pk=%s", key)
                return False
            raise

    async def mark_done(self, key: str) -> None:
        await _run(
            self._table.update_item,
            Key={"pk": key},
            UpdateExpression="SET #s = :done",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":done": "DONE"},
        )
        logger.debug("pending_action | marked done pk=%s", key)
