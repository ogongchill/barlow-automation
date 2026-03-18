"""WorkflowInstance 직렬화/역직렬화 테스트."""

from src.workflow.models.workflow_instance import WorkflowInstance
from src.workflow.models.lifecycle import WorkflowStatus


def test_workflow_instance_to_item_has_required_keys(feat_workflow_instance):
    item = feat_workflow_instance.to_item()
    for key in ["workflow_id", "workflow_type", "status", "current_step", "state", "ttl"]:
        assert key in item


def test_workflow_instance_roundtrip(feat_workflow_instance):
    restored = WorkflowInstance.from_item(feat_workflow_instance.to_item())
    assert restored.workflow_id == feat_workflow_instance.workflow_id
    assert restored.workflow_type == feat_workflow_instance.workflow_type
    assert restored.status == feat_workflow_instance.status
    assert restored.current_step == feat_workflow_instance.current_step


def test_workflow_instance_default_status_is_created():
    instance = WorkflowInstance.create(
        workflow_type="feat_issue",
        slack_channel_id="C1",
        slack_user_id="U1",
        user_message="test",
    )
    assert instance.status == WorkflowStatus.CREATED


def test_workflow_instance_ttl_positive(feat_workflow_instance):
    assert feat_workflow_instance.ttl > 0
