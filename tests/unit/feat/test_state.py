"""FeatIssueWorkflowState 테스트."""
from src.domain.feat.models.state import FeatIssueWorkflowState


def test_apply_patch_updates_field():
    state = FeatIssueWorkflowState(user_message="msg")
    state.apply_patch({"bc_candidates": '{"items":[]}'})
    assert state.bc_candidates == '{"items":[]}'


def test_apply_patch_ignores_unknown_field():
    state = FeatIssueWorkflowState(user_message="msg")
    state.apply_patch({"nonexistent_field": "value"})
    assert not hasattr(state, "nonexistent_field")


def test_apply_patch_multiple_fields():
    state = FeatIssueWorkflowState(user_message="msg")
    state.apply_patch({"bc_candidates": "{}", "issue_draft": '{"title":"T"}'})
    assert state.bc_candidates == "{}"
    assert state.issue_draft == '{"title":"T"}'


def test_to_dict_roundtrip():
    state = FeatIssueWorkflowState(
        user_message="msg",
        bc_candidates='{"items":[]}',
    )
    d = state.to_dict()
    restored = FeatIssueWorkflowState.from_dict(d)
    assert restored.user_message == "msg"
    assert restored.bc_candidates == '{"items":[]}'


def test_dropped_item_ids_default_empty():
    state = FeatIssueWorkflowState(user_message="msg")
    assert state.dropped_item_ids == []
