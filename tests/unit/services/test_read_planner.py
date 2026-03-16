"""run_read_planner service tests -- mock AgentFactory."""

from unittest.mock import patch, AsyncMock

import pytest

from src.agent.base import AgentResult
from src.agent.usage import AgentUsage


@pytest.fixture()
def mock_planner_agent():
    agent = AsyncMock()
    agent.run.return_value = AgentResult(
        output="planner output text",
        usage=AgentUsage(input_tokens=100, output_tokens=50),
    )
    return agent


@pytest.fixture()
def mock_inspector_agent():
    agent = AsyncMock()
    agent.run.return_value = AgentResult(
        output="inspector output text",
        usage=AgentUsage(input_tokens=200, output_tokens=80),
    )
    return agent


class TestRunReadPlanner:

    @patch("src.services.read_planner.AgentFactory")
    async def test_call_order_planner_then_inspector(
        self, mock_factory, mock_planner_agent, mock_inspector_agent
    ) -> None:
        mock_factory.read_planner.return_value = mock_planner_agent
        mock_factory.inspector.return_value = mock_inspector_agent

        from src.services.read_planner import run_read_planner

        output, usage = await run_read_planner("user request")

        mock_planner_agent.run.assert_awaited_once_with("user request")
        mock_inspector_agent.run.assert_awaited_once_with("planner output text")

    @patch("src.services.read_planner.AgentFactory")
    async def test_returns_inspector_output(
        self, mock_factory, mock_planner_agent, mock_inspector_agent
    ) -> None:
        mock_factory.read_planner.return_value = mock_planner_agent
        mock_factory.inspector.return_value = mock_inspector_agent

        from src.services.read_planner import run_read_planner

        output, usage = await run_read_planner("user request")
        assert output == "inspector output text"

    @patch("src.services.read_planner.AgentFactory")
    async def test_usage_accumulation(
        self, mock_factory, mock_planner_agent, mock_inspector_agent
    ) -> None:
        mock_factory.read_planner.return_value = mock_planner_agent
        mock_factory.inspector.return_value = mock_inspector_agent

        from src.services.read_planner import run_read_planner

        output, usage = await run_read_planner("user request")
        assert usage.input_tokens == 300   # 100 + 200
        assert usage.output_tokens == 130  # 50 + 80
