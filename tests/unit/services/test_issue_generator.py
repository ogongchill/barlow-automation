"""run_issue_generator service tests."""

from unittest.mock import patch, AsyncMock

import pytest

from src.agent.base import AgentResult
from src.agent.usage import AgentUsage
from src.domain.issue_templates import FeatTemplate


class TestRunIssueGenerator:

    @patch("src.services.issue_generator.AgentFactory")
    async def test_returns_typed_output(self, mock_factory, feat_template) -> None:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = AgentResult(
            output="raw text",
            usage=AgentUsage(input_tokens=50, output_tokens=30),
            typed_output=feat_template,
        )
        mock_factory.issue_gen.return_value = mock_agent

        from src.services.issue_generator import run_issue_generator

        template, usage = await run_issue_generator("feat", "inspector output")
        assert template is feat_template
        assert usage.input_tokens == 50
        assert usage.output_tokens == 30

    @patch("src.services.issue_generator.AgentFactory")
    async def test_correct_subcommand_passed(self, mock_factory, feat_template) -> None:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = AgentResult(
            output="raw text",
            usage=AgentUsage(input_tokens=10, output_tokens=5),
            typed_output=feat_template,
        )
        mock_factory.issue_gen.return_value = mock_agent

        from src.services.issue_generator import run_issue_generator

        await run_issue_generator("feat", "bc finder output")
        mock_factory.issue_gen.assert_called_once_with("feat")

    @patch("src.services.issue_generator.AgentFactory")
    async def test_agent_receives_inspector_output(self, mock_factory, feat_template) -> None:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = AgentResult(
            output="raw text",
            usage=AgentUsage(input_tokens=10, output_tokens=5),
            typed_output=feat_template,
        )
        mock_factory.issue_gen.return_value = mock_agent

        from src.services.issue_generator import run_issue_generator

        await run_issue_generator("refactor", "some bc finder text")
        mock_agent.run.assert_awaited_once_with("some bc finder text")
