"""GenerateIssueDraftStep unit tests -- Phase 3 of test-plan."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.workflow.steps.feat_issue.generate_issue_draft_step import GenerateIssueDraftStep
from src.workflow.models.workflow_state import FeatIssueWorkflowState


@pytest.fixture
def state_with_bc_decision():
    state = FeatIssueWorkflowState(user_message="[feat] bookmark")
    state.bc_candidates = '{"items":[{"bounded_context":"OrderContext"}]}'
    state.bc_decision = '{"primary_context":"OrderContext","rationale":"..."}'
    return state


async def test_prompt_includes_bc_decision(state_with_bc_decision, make_agent_result, feat_template):
    step = GenerateIssueDraftStep(subcommand="feat")
    mock_agent = AsyncMock()
    mock_agent.run.return_value = make_agent_result(output="", typed_output=feat_template)

    with patch(
        "src.workflow.steps.feat_issue.generate_issue_draft_step.AgentExecutor"
    ) as mock_executor_cls:
        mock_executor_cls.build.return_value = mock_agent
        await step.execute(state_with_bc_decision)

    prompt = mock_agent.run.call_args[0][0]
    assert "OrderContext" in prompt


async def test_result_patches_issue_draft(state_with_bc_decision, make_agent_result, feat_template):
    step = GenerateIssueDraftStep(subcommand="feat")
    mock_agent = AsyncMock()
    mock_agent.run.return_value = make_agent_result(output="", typed_output=feat_template)

    with patch(
        "src.workflow.steps.feat_issue.generate_issue_draft_step.AgentExecutor"
    ) as mock_executor_cls:
        mock_executor_cls.build.return_value = mock_agent
        result = await step.execute(state_with_bc_decision)

    assert "issue_draft" in result.state_patch


async def test_result_status_is_success(state_with_bc_decision, make_agent_result, feat_template):
    step = GenerateIssueDraftStep(subcommand="feat")
    mock_agent = AsyncMock()
    mock_agent.run.return_value = make_agent_result(output="", typed_output=feat_template)

    with patch(
        "src.workflow.steps.feat_issue.generate_issue_draft_step.AgentExecutor"
    ) as mock_executor_cls:
        mock_executor_cls.build.return_value = mock_agent
        result = await step.execute(state_with_bc_decision)

    assert result.status == "success"
    assert result.control_signal == "continue"


async def test_unknown_subcommand_raises():
    step = GenerateIssueDraftStep(subcommand="unknown")
    state = FeatIssueWorkflowState(user_message="test")
    with pytest.raises(ValueError, match="Unknown subcommand"):
        await step.execute(state)


async def test_prompt_includes_bc_candidates_section(state_with_bc_decision, make_agent_result, feat_template):
    step = GenerateIssueDraftStep(subcommand="feat")
    mock_agent = AsyncMock()
    mock_agent.run.return_value = make_agent_result(output="", typed_output=feat_template)

    with patch(
        "src.workflow.steps.feat_issue.generate_issue_draft_step.AgentExecutor"
    ) as mock_executor_cls:
        mock_executor_cls.build.return_value = mock_agent
        await step.execute(state_with_bc_decision)

    prompt = mock_agent.run.call_args[0][0]
    assert "[BC Finder Candidates]" in prompt
    assert "[BC Decision]" in prompt
