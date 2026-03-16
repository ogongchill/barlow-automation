"""barlow-pending DynamoDB 테이블 CRUD — IPendingRepository 구현체."""

import asyncio
import logging
from functools import partial

import boto3

from src.domain.pending import IPendingRepository, PendingRecord

logger = logging.getLogger(__name__)

TABLE_NAME = "barlow-pending"


async def _run(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))


def _to_dynamo_type(value) -> dict:
    """Python 값을 DynamoDB 타입 표현으로 변환한다."""
    if isinstance(value, str):
        return {"S": value}
    if isinstance(value, int):
        return {"N": str(value)}
    raise TypeError(f"Unsupported DynamoDB type: {type(value)}")


class DynamoPendingRepository(IPendingRepository):
    """barlow-pending DynamoDB 테이블 기반 IPendingRepository 구현체."""

    def __init__(self) -> None:
        self._table = boto3.resource("dynamodb").Table(TABLE_NAME)
        self._client = boto3.client("dynamodb")

    async def save(self, record: PendingRecord) -> None:
        await _run(self._table.put_item, Item=record.to_item())
        logger.debug("pending | saved pk=%s", record.pk)

    async def get(self, message_ts: str) -> PendingRecord | None:
        response = await _run(self._table.get_item, Key={"pk": message_ts})
        item = response.get("Item")
        if not item:
            return None
        return PendingRecord.from_item(item)

    async def save_new_and_delete_old(self, new_record: PendingRecord, old_ts: str) -> None:
        """새 레코드를 저장하고 기존 레코드를 원자적으로 삭제한다."""
        await _run(
            self._client.transact_write_items,
            TransactItems=[
                {
                    "Put": {
                        "TableName": TABLE_NAME,
                        "Item": {k: _to_dynamo_type(v) for k, v in new_record.to_item().items()},
                    }
                },
                {
                    "Delete": {
                        "TableName": TABLE_NAME,
                        "Key": {"pk": {"S": old_ts}},
                    }
                },
            ],
        )
        logger.debug("pending | rotated old_ts=%s -> new_ts=%s", old_ts, new_record.pk)

    async def delete(self, message_ts: str) -> None:
        await _run(self._table.delete_item, Key={"pk": message_ts})
        logger.debug("pending | deleted pk=%s", message_ts)
