"""WorkflowInstance 직렬화/역직렬화 및 생성 테스트."""
import time

from src.domain.common.models.workflow_instance import WorkflowInstance
from src.domain.common.models.lifecycle import WorkflowStatus
from src.domain.feat.models.state import FeatIssueWorkflowState


def test_create_sets_first_step():
    instance = WorkflowInstance.create("feat_issue", "C1", "U1", "msg")
    assert instance.current_step == "find_relevant_bc"
    assert instance.status == WorkflowStatus.CREATED
    assert instance.workflow_id is not None


def test_create_sets_workflow_type():
    instance = WorkflowInstance.create("feat_issue", "C1", "U1", "msg")
    assert instance.workflow_type == "feat_issue"
    assert instance.slack_channel_id == "C1"
    assert instance.slack_user_id == "U1"


def test_to_item_from_item_roundtrip():
    instance = WorkflowInstance.create("feat_issue", "C1", "U1", "msg")
    item = instance.to_item()
    restored = WorkflowInstance.from_item(item)

    assert restored.workflow_id == instance.workflow_id
    assert restored.workflow_type == instance.workflow_type
    assert restored.status == instance.status
    assert restored.current_step == instance.current_step
    assert restored.slack_channel_id == instance.slack_channel_id
    assert restored.slack_user_id == instance.slack_user_id


def test_to_item_contains_required_keys():
    instance = WorkflowInstance.create("feat_issue", "C1", "U1", "msg")
    item = instance.to_item()

    required = {"workflow_id", "workflow_type", "status", "current_step",
                "state", "slack_channel_id", "slack_user_id", "created_at", "ttl"}
    assert required.issubset(item.keys())


def test_from_item_restores_state_user_message():
    instance = WorkflowInstance.create("feat_issue", "C1", "U1", "hello world")
    restored = WorkflowInstance.from_item(instance.to_item())
    assert restored.state.user_message == "hello world"


def test_ttl_is_in_future():
    instance = WorkflowInstance.create("feat_issue", "C1", "U1", "msg")
    assert instance.ttl > int(time.time())
