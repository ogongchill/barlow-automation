"""FeatIssueWorkflowState state_patch 적용 테스트."""

from src.workflow.models.workflow_state import FeatIssueWorkflowState


def test_apply_patch_updates_fields(feat_workflow_state):
    patch = {"bc_candidates": '{"items": []}', "user_feedback": None}
    feat_workflow_state.apply_patch(patch)
    assert feat_workflow_state.bc_candidates is not None


def test_initial_state_all_none_except_user_message(feat_workflow_state):
    assert feat_workflow_state.bc_candidates is None
    assert feat_workflow_state.bc_decision is None
    assert feat_workflow_state.issue_draft is None
    assert feat_workflow_state.github_issue_url is None
