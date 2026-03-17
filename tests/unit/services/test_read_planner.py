"""run_read_planner service tests -- mock AgentFactory."""

from unittest.mock import patch, AsyncMock

import pytest

from src.agent.base import AgentResult
from src.agent.usage import AgentUsage


@pytest.fixture()
def mock_bc_finder_agent():
    agent = AsyncMock()
    agent.run.return_value = AgentResult(
        output="bc finder output text",
        usage=AgentUsage(input_tokens=200, output_tokens=80),
    )
    return agent


class TestRunReadPlanner:

    @patch("src.services.read_planner.AgentFactory")
    async def test_calls_bc_finder_with_user_message(
        self, mock_factory, mock_bc_finder_agent
    ) -> None:
        mock_factory.relevant_bc_finder.return_value = mock_bc_finder_agent

        from src.services.read_planner import run_read_planner

        await run_read_planner("user request")

        mock_bc_finder_agent.run.assert_awaited_once_with("user request")

    @patch("src.services.read_planner.AgentFactory")
    async def test_returns_bc_finder_output(
        self, mock_factory, mock_bc_finder_agent
    ) -> None:
        mock_factory.relevant_bc_finder.return_value = mock_bc_finder_agent

        from src.services.read_planner import run_read_planner

        output, usage = await run_read_planner("user request")
        assert output == "bc finder output text"

    @patch("src.services.read_planner.AgentFactory")
    async def test_usage_accumulation(
        self, mock_factory, mock_bc_finder_agent
    ) -> None:
        mock_factory.relevant_bc_finder.return_value = mock_bc_finder_agent

        from src.services.read_planner import run_read_planner

        output, usage = await run_read_planner("user request")
        assert usage.input_tokens == 200
        assert usage.output_tokens == 80
