"""PendingAction DynamoDB store 단위 테스트."""

import pytest
from moto import mock_aws

TABLE_NAME = "barlow-pending-action"


def _restore_boto3(monkeypatch):
    """conftest에서 mock된 boto3를 mock_aws 내에서 복원한다."""
    import boto3

    def _client(*a, **kw):
        return boto3.session.Session().client(*a, **kw)

    def _resource(*a, **kw):
        return boto3.session.Session().resource(*a, **kw)

    monkeypatch.setattr(boto3, "client", _client)
    monkeypatch.setattr(boto3, "resource", _resource)


@pytest.fixture()
def dynamo_env(monkeypatch):
    """mock_aws 내에서 real boto3를 복원하고 테이블을 생성한다."""
    with mock_aws():
        _restore_boto3(monkeypatch)
        import boto3
        client = boto3.client(
            "dynamodb", region_name="ap-northeast-2",
        )
        client.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


async def test_try_acquire_returns_true_first_time(dynamo_env):
    from src.infrastructure.storage.dynamodb.pending_action_store import (
        DynamoPendingActionStore,
    )
    store = DynamoPendingActionStore(table_name=TABLE_NAME)
    assert await store.try_acquire("action-1") is True


async def test_try_acquire_returns_false_for_duplicate(dynamo_env):
    from src.infrastructure.storage.dynamodb.pending_action_store import (
        DynamoPendingActionStore,
    )
    store = DynamoPendingActionStore(table_name=TABLE_NAME)
    await store.try_acquire("action-1")
    assert await store.try_acquire("action-1") is False


async def test_mark_done_succeeds(dynamo_env):
    from src.infrastructure.storage.dynamodb.pending_action_store import (
        DynamoPendingActionStore,
    )
    store = DynamoPendingActionStore(table_name=TABLE_NAME)
    await store.try_acquire("action-2")
    await store.mark_done("action-2")
