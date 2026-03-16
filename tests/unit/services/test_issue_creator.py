"""run_issue_creator service tests — service does not exist yet, tests expected to fail."""

from unittest.mock import patch, AsyncMock

import pytest

from src.agent.base import AgentResult
from src.agent.usage import AgentUsage
from src.domain.pending import PendingRecord


def _make_record(template, subcommand: str = "feat") -> PendingRecord:
    return PendingRecord(
        pk="ts_123",
        subcommand=subcommand,
        user_id="U1",
        channel_id="C1",
        user_message="[feat] bookmark",
        inspector_output="inspector context",
        typed_output=template,
    )


class TestRunIssueCreator:

    @patch("src.services.issue_creator.AgentFactory")
    async def test_issue_creator_calls_issue_writer_factory(
        self, mock_factory, feat_template
    ) -> None:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = AgentResult(
            output="https://github.com/owner/repo/issues/42",
            usage=AgentUsage(input_tokens=10, output_tokens=5),
        )
        mock_factory.issue_writer.return_value = mock_agent

        from src.services.issue_creator import run_issue_creator

        record = _make_record(feat_template, subcommand="feat")
        await run_issue_creator(record)

        mock_factory.issue_writer.assert_called_once_with("feat")

    @patch("src.services.issue_creator.AgentFactory")
    async def test_issue_creator_runs_agent_and_returns_url(
        self, mock_factory, feat_template, make_agent_result
    ) -> None:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = make_agent_result(
            output="https://github.com/owner/repo/issues/42"
        )
        mock_factory.issue_writer.return_value = mock_agent

        from src.services.issue_creator import run_issue_creator

        record = _make_record(feat_template)
        url = await run_issue_creator(record)

        assert "github.com" in url

    @patch("src.services.issue_creator.AgentFactory")
    async def test_issue_creator_prompt_contains_template_title(
        self, mock_factory, feat_template, make_agent_result
    ) -> None:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = make_agent_result(
            output="https://github.com/owner/repo/issues/1"
        )
        mock_factory.issue_writer.return_value = mock_agent

        from src.services.issue_creator import run_issue_creator

        record = _make_record(feat_template)
        await run_issue_creator(record)

        prompt_arg = mock_agent.run.call_args[0][0]
        assert feat_template.issue_title in prompt_arg

    @patch("src.services.issue_creator.AgentFactory")
    async def test_issue_creator_routes_refactor_subcommand(
        self, mock_factory, refactor_template, make_agent_result
    ) -> None:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = make_agent_result(
            output="https://github.com/owner/repo/issues/99"
        )
        mock_factory.issue_writer.return_value = mock_agent

        from src.services.issue_creator import run_issue_creator

        record = _make_record(refactor_template, subcommand="refactor")
        await run_issue_creator(record)

        mock_factory.issue_writer.assert_called_once_with("refactor")
