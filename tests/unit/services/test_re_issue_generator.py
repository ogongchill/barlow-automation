"""run_re_issue_generator service tests."""

from unittest.mock import patch, AsyncMock

import pytest

from src.agent.base import AgentResult
from src.agent.usage import AgentUsage
from src.domain.issue_templates import FeatTemplate
from src.domain.pending import PendingRecord


def _make_pending(feat_template: FeatTemplate) -> PendingRecord:
    return PendingRecord(
        pk="ts_123",
        subcommand="feat",
        user_id="U1",
        channel_id="C1",
        user_message="original prompt",
        bc_finder_output="bc finder context here",
        typed_output=feat_template,
    )


class TestRunReIssueGenerator:

    @patch("src.services.re_issue_generator.AgentFactory")
    async def test_prompt_contains_inspector_context(
        self, mock_factory, feat_template
    ) -> None:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = AgentResult(
            output="raw",
            usage=AgentUsage(input_tokens=10, output_tokens=5),
            typed_output=feat_template,
        )
        mock_factory.reissue_gen.return_value = mock_agent

        from src.services.re_issue_generator import run_re_issue_generator

        record = _make_pending(feat_template)
        await run_re_issue_generator(record, "add caching")

        call_args = mock_agent.run.call_args[0][0]
        assert "[BC Finder Context]" in call_args
        assert "bc finder context here" in call_args

    @patch("src.services.re_issue_generator.AgentFactory")
    async def test_prompt_contains_current_issue_draft(
        self, mock_factory, feat_template
    ) -> None:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = AgentResult(
            output="raw",
            usage=AgentUsage(input_tokens=10, output_tokens=5),
            typed_output=feat_template,
        )
        mock_factory.reissue_gen.return_value = mock_agent

        from src.services.re_issue_generator import run_re_issue_generator

        record = _make_pending(feat_template)
        await run_re_issue_generator(record)

        call_args = mock_agent.run.call_args[0][0]
        assert "[Current Issue Draft]" in call_args

    @patch("src.services.re_issue_generator.AgentFactory")
    async def test_prompt_contains_additional_requirements(
        self, mock_factory, feat_template
    ) -> None:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = AgentResult(
            output="raw",
            usage=AgentUsage(input_tokens=10, output_tokens=5),
            typed_output=feat_template,
        )
        mock_factory.reissue_gen.return_value = mock_agent

        from src.services.re_issue_generator import run_re_issue_generator

        record = _make_pending(feat_template)
        await run_re_issue_generator(record, "please add caching")

        call_args = mock_agent.run.call_args[0][0]
        assert "Additional requirements: please add caching" in call_args

    @patch("src.services.re_issue_generator.AgentFactory")
    async def test_prompt_omits_additional_when_none(
        self, mock_factory, feat_template
    ) -> None:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = AgentResult(
            output="raw",
            usage=AgentUsage(input_tokens=10, output_tokens=5),
            typed_output=feat_template,
        )
        mock_factory.reissue_gen.return_value = mock_agent

        from src.services.re_issue_generator import run_re_issue_generator

        record = _make_pending(feat_template)
        await run_re_issue_generator(record, None)

        call_args = mock_agent.run.call_args[0][0]
        assert "Additional requirements" not in call_args

    @patch("src.services.re_issue_generator.AgentFactory")
    async def test_returns_typed_output(self, mock_factory, feat_template) -> None:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = AgentResult(
            output="raw",
            usage=AgentUsage(input_tokens=10, output_tokens=5),
            typed_output=feat_template,
        )
        mock_factory.reissue_gen.return_value = mock_agent

        from src.services.re_issue_generator import run_re_issue_generator

        record = _make_pending(feat_template)
        template, usage = await run_re_issue_generator(record)
        assert template is feat_template
