"""DynamoActiveSessionStore -- 활성 세션 DynamoDB 저장소."""

import asyncio
import logging
import os
import time
from functools import partial

import boto3

from src.domain.common.ports.active_session import IActiveSessionRepository

logger = logging.getLogger(__name__)

def _require_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return value


TABLE_NAME = _require_env("ACTIVE_SESSION_TABLE_NAME")
SESSION_TTL_SECONDS = 60 * 60 * 24  # 24시간


async def _run(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))


class DynamoActiveSessionStore(IActiveSessionRepository):
    """barlow-active-session DynamoDB 테이블 기반 활성 세션 저장소."""

    def __init__(self, table_name: str | None = None) -> None:
        self._table_name = table_name or TABLE_NAME
        self._table = boto3.resource(
            "dynamodb", region_name="ap-northeast-2"
        ).Table(self._table_name)

    def _key(self, channel_id: str, user_id: str) -> str:
        return f"{channel_id}#{user_id}"

    async def get_workflow_id(self, channel_id: str, user_id: str) -> str | None:
        response = await _run(
            self._table.get_item, Key={"pk": self._key(channel_id, user_id)}
        )
        item = response.get("Item")
        return item["workflow_id"] if item else None

    async def set(self, channel_id: str, user_id: str, workflow_id: str) -> None:
        await _run(
            self._table.put_item,
            Item={
                "pk": self._key(channel_id, user_id),
                "workflow_id": workflow_id,
                "ttl": int(time.time()) + SESSION_TTL_SECONDS,
            },
        )
        logger.debug(
            "active_session | set channel=%s user=%s workflow_id=%s",
            channel_id, user_id, workflow_id,
        )

    async def clear(self, channel_id: str, user_id: str) -> None:
        await _run(
            self._table.delete_item, Key={"pk": self._key(channel_id, user_id)}
        )
        logger.debug(
            "active_session | cleared channel=%s user=%s", channel_id, user_id
        )
