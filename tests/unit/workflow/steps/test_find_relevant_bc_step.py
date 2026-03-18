"""FindRelevantBcStep unit tests -- Phase 3 of test-plan."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.workflow.steps.feat_issue.find_relevant_bc_step import FindRelevantBcStep
from src.workflow.models.workflow_state import FeatIssueWorkflowState


async def test_step_returns_success_result(feat_workflow_state, make_agent_result):
    step = FindRelevantBcStep()
    mock_agent = AsyncMock()
    mock_agent.run.return_value = make_agent_result(output='{"items":[]}')

    with patch(
        "src.workflow.steps.feat_issue.find_relevant_bc_step.AgentExecutor"
    ) as mock_executor_cls:
        mock_executor_cls.build.return_value = mock_agent
        result = await step.execute(feat_workflow_state)

    assert result.status == "success"
    assert result.control_signal == "continue"


async def test_step_patches_bc_candidates(feat_workflow_state, make_agent_result):
    step = FindRelevantBcStep()
    mock_agent = AsyncMock()
    mock_agent.run.return_value = make_agent_result(
        output='{"items":[{"bounded_context":"OrderContext"}]}'
    )

    with patch(
        "src.workflow.steps.feat_issue.find_relevant_bc_step.AgentExecutor"
    ) as mock_executor_cls:
        mock_executor_cls.build.return_value = mock_agent
        result = await step.execute(feat_workflow_state)

    assert "bc_candidates" in result.state_patch


async def test_step_receives_user_message(feat_workflow_state, make_agent_result):
    step = FindRelevantBcStep()
    mock_agent = AsyncMock()
    mock_agent.run.return_value = make_agent_result(output='{"items":[]}')

    with patch(
        "src.workflow.steps.feat_issue.find_relevant_bc_step.AgentExecutor"
    ) as mock_executor_cls:
        mock_executor_cls.build.return_value = mock_agent
        await step.execute(feat_workflow_state)

    call_args = mock_agent.run.call_args[0][0]
    assert feat_workflow_state.user_message in call_args


async def test_step_internal_trace_has_token_usage(feat_workflow_state, make_agent_result):
    step = FindRelevantBcStep()
    mock_agent = AsyncMock()
    mock_agent.run.return_value = make_agent_result(output='{}', in_tokens=100, out_tokens=50)

    with patch(
        "src.workflow.steps.feat_issue.find_relevant_bc_step.AgentExecutor"
    ) as mock_executor_cls:
        mock_executor_cls.build.return_value = mock_agent
        result = await step.execute(feat_workflow_state)

    assert result.internal_trace["input_tokens"] == 100
    assert result.internal_trace["output_tokens"] == 50
