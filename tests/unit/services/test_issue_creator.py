"""run_issue_creator service tests -- GitHub REST API mock."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.pending import PendingRecord


def _make_record(template, subcommand: str = "feat") -> PendingRecord:
    return PendingRecord(
        pk="ts_123",
        subcommand=subcommand,
        user_id="U1",
        channel_id="C1",
        user_message="[feat] bookmark",
        bc_finder_output="bc finder context",
        typed_output=template,
    )


def _mock_http_client(issue_url: str = "https://github.com/owner/repo/issues/1"):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"html_url": issue_url}
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)
    return mock_client


class TestRunIssueCreator:

    @patch("src.services.issue_creator.httpx.AsyncClient")
    async def test_returns_issue_url(self, mock_client_cls, feat_template) -> None:
        expected_url = "https://github.com/owner/repo/issues/42"
        mock_client_cls.return_value = _mock_http_client(expected_url)

        from src.services.issue_creator import run_issue_creator

        record = _make_record(feat_template)
        url = await run_issue_creator(record)

        assert url == expected_url

    @patch("src.services.issue_creator.httpx.AsyncClient")
    async def test_post_called_with_correct_title(self, mock_client_cls, feat_template) -> None:
        mock_client = _mock_http_client()
        mock_client_cls.return_value = mock_client

        from src.services.issue_creator import run_issue_creator

        record = _make_record(feat_template)
        await run_issue_creator(record)

        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["title"] == feat_template.issue_title

    @patch("src.services.issue_creator.httpx.AsyncClient")
    async def test_feat_label_is_set(self, mock_client_cls, feat_template) -> None:
        mock_client = _mock_http_client()
        mock_client_cls.return_value = mock_client

        from src.services.issue_creator import run_issue_creator

        record = _make_record(feat_template, subcommand="feat")
        await run_issue_creator(record)

        call_kwargs = mock_client.post.call_args.kwargs
        assert "feat" in call_kwargs["json"]["labels"]

    @patch("src.services.issue_creator.httpx.AsyncClient")
    async def test_refactor_label_is_set(self, mock_client_cls, refactor_template) -> None:
        mock_client = _mock_http_client()
        mock_client_cls.return_value = mock_client

        from src.services.issue_creator import run_issue_creator

        record = _make_record(refactor_template, subcommand="refactor")
        await run_issue_creator(record)

        call_kwargs = mock_client.post.call_args.kwargs
        assert "refactor" in call_kwargs["json"]["labels"]

    @patch("src.services.issue_creator.httpx.AsyncClient")
    async def test_body_contains_about(self, mock_client_cls, feat_template) -> None:
        mock_client = _mock_http_client()
        mock_client_cls.return_value = mock_client

        from src.services.issue_creator import run_issue_creator

        record = _make_record(feat_template)
        await run_issue_creator(record)

        call_kwargs = mock_client.post.call_args.kwargs
        assert feat_template.about in call_kwargs["json"]["body"]
