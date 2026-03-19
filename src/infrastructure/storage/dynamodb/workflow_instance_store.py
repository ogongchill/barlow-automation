"""WorkflowInstance DynamoDB 저장소 구현."""

import asyncio
import logging
import os
from functools import partial

import boto3

from src.domain.common.models.workflow_instance import IWorkflowInstanceRepository, WorkflowInstance

logger = logging.getLogger(__name__)

TABLE_NAME = os.environ.get("WORKFLOW_TABLE_NAME", "barlow-workflow")


async def _run(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))


class DynamoWorkflowInstanceStore(IWorkflowInstanceRepository):
    """barlow-workflow DynamoDB 테이블 기반 IWorkflowInstanceRepository 구현체."""

    def __init__(self, table_name: str | None = None) -> None:
        self._table_name = table_name or TABLE_NAME
        self._table = boto3.resource("dynamodb", region_name="ap-northeast-2").Table(self._table_name)

    async def save(self, instance: WorkflowInstance) -> None:
        await _run(self._table.put_item, Item=instance.to_item())
        logger.debug("workflow_instance | saved workflow_id=%s", instance.workflow_id)

    async def get(self, workflow_id: str) -> WorkflowInstance | None:
        response = await _run(self._table.get_item, Key={"workflow_id": workflow_id})
        item = response.get("Item")
        if not item:
            return None
        return WorkflowInstance.from_item(item)
