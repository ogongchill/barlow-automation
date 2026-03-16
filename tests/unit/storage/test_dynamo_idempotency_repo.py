"""DynamoIdempotencyRepository unit tests — boto3 is globally mocked in conftest."""

import pytest
from botocore.exceptions import ClientError

from src.storage.idempotency_dynamo_repository import DynamoIdempotencyRepository


@pytest.fixture()
def repo() -> DynamoIdempotencyRepository:
    r = DynamoIdempotencyRepository()
    r._table.put_item.side_effect = None
    r._table.put_item.reset_mock()
    r._table.update_item.reset_mock()
    return r


class TestTryAcquire:

    async def test_try_acquire_returns_true_on_success(self, repo) -> None:
        result = await repo.try_acquire("d1")

        assert result is True
        repo._table.put_item.assert_called_once()
        call_kwargs = repo._table.put_item.call_args.kwargs
        assert call_kwargs["ConditionExpression"] == "attribute_not_exists(pk)"

    async def test_try_acquire_returns_false_on_conditional_check_failed(self, repo) -> None:
        repo._table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": ""}},
            "PutItem",
        )

        result = await repo.try_acquire("dup_id")

        assert result is False

    async def test_try_acquire_reraises_other_client_errors(self, repo) -> None:
        repo._table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": ""}},
            "PutItem",
        )

        with pytest.raises(ClientError):
            await repo.try_acquire("d1")


class TestMarkDone:

    async def test_mark_done_calls_update_item_with_done_status(self, repo) -> None:
        await repo.mark_done("d1")

        repo._table.update_item.assert_called_once()
        call_kwargs = repo._table.update_item.call_args.kwargs
        assert call_kwargs["Key"]["pk"] == "d1"
        assert ":done" in call_kwargs["ExpressionAttributeValues"]
        assert call_kwargs["ExpressionAttributeValues"][":done"] == "DONE"
