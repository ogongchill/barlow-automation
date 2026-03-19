"""FindRelevantBcStep 단위 테스트."""
from unittest.mock import AsyncMock, MagicMock, patch

from src.domain.feat.models.state import FeatIssueWorkflowState
from src.domain.feat.steps.find_relevant_bc import FindRelevantBcStep


async def test_execute_returns_bc_candidates_in_patch():
    mock_agent = AsyncMock()
    mock_agent.run.return_value = MagicMock(
        output='{"items":[]}',
        usage=MagicMock(input_tokens=10, output_tokens=5),
    )

    with patch(
        "src.domain.feat.steps.find_relevant_bc.FeatAgentExecutor.build",
        return_value=mock_agent,
    ):
        step = FindRelevantBcStep()
        state = FeatIssueWorkflowState(user_message="북마크 기능 추가")
        result = await step.execute(state)

    assert result.status == "success"
    assert result.control_signal == "continue"
    assert result.state_patch["bc_candidates"] == '{"items":[]}'


async def test_execute_passes_user_message_to_agent():
    mock_agent = AsyncMock()
    mock_agent.run.return_value = MagicMock(
        output="{}",
        usage=MagicMock(input_tokens=1, output_tokens=1),
    )

    with patch(
        "src.domain.feat.steps.find_relevant_bc.FeatAgentExecutor.build",
        return_value=mock_agent,
    ):
        step = FindRelevantBcStep()
        state = FeatIssueWorkflowState(user_message="my request")
        await step.execute(state)

    mock_agent.run.assert_called_once_with("my request")


async def test_execute_includes_token_trace():
    mock_agent = AsyncMock()
    mock_agent.run.return_value = MagicMock(
        output="{}",
        usage=MagicMock(input_tokens=100, output_tokens=50),
    )

    with patch(
        "src.domain.feat.steps.find_relevant_bc.FeatAgentExecutor.build",
        return_value=mock_agent,
    ):
        step = FindRelevantBcStep()
        state = FeatIssueWorkflowState(user_message="msg")
        result = await step.execute(state)

    assert result.internal_trace["input_tokens"] == 100
    assert result.internal_trace["output_tokens"] == 50
