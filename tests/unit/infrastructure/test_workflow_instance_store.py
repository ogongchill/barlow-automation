"""WorkflowInstance DynamoDB store 단위 테스트."""

import time

import pytest
from moto import mock_aws

from src.workflow.models.lifecycle import WorkflowStatus
from src.workflow.models.workflow_instance import WorkflowInstance
from src.workflow.models.workflow_state import FeatIssueWorkflowState

TABLE_NAME = "barlow-workflow"


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
                {"AttributeName": "workflow_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "workflow_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


@pytest.fixture()
def _workflow_instance():
    now = int(time.time())
    return WorkflowInstance(
        workflow_id="wf-test-001",
        workflow_type="feat_issue",
        status=WorkflowStatus.RUNNING,
        current_step="find_relevant_bc",
        state=FeatIssueWorkflowState(user_message="test"),
        pending_action_token=None,
        slack_channel_id="C1",
        slack_user_id="U1",
        slack_message_ts=None,
        created_at=now,
        ttl=now + 86400,
    )


async def test_save_and_get_roundtrip(dynamo_env, _workflow_instance):
    from src.infrastructure.storage.dynamodb.workflow_instance_store import (
        DynamoWorkflowInstanceStore,
    )
    store = DynamoWorkflowInstanceStore(table_name=TABLE_NAME)
    await store.save(_workflow_instance)
    restored = await store.get(_workflow_instance.workflow_id)
    assert restored is not None
    assert restored.workflow_id == _workflow_instance.workflow_id
    assert restored.status == _workflow_instance.status


async def test_get_nonexistent_returns_none(dynamo_env):
    from src.infrastructure.storage.dynamodb.workflow_instance_store import (
        DynamoWorkflowInstanceStore,
    )
    store = DynamoWorkflowInstanceStore(table_name=TABLE_NAME)
    result = await store.get("nonexistent-id")
    assert result is None


async def test_save_overwrites_existing(dynamo_env, _workflow_instance):
    from src.infrastructure.storage.dynamodb.workflow_instance_store import (
        DynamoWorkflowInstanceStore,
    )
    store = DynamoWorkflowInstanceStore(table_name=TABLE_NAME)
    await store.save(_workflow_instance)
    _workflow_instance.status = WorkflowStatus.COMPLETED
    await store.save(_workflow_instance)
    restored = await store.get(_workflow_instance.workflow_id)
    assert restored is not None
    assert restored.status == WorkflowStatus.COMPLETED
