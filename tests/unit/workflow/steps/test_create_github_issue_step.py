"""CreateGithubIssueStep unit tests -- Phase 3 of test-plan."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from src.workflow.steps.feat_issue.create_github_issue_step import CreateGithubIssueStep
from src.workflow.models.workflow_state import FeatIssueWorkflowState


@pytest.fixture
def state_with_issue_draft(feat_template):
    state = FeatIssueWorkflowState(user_message="[feat] bookmark")
    state.issue_draft = feat_template.model_dump_json()
    return state


async def test_step_calls_github_api(state_with_issue_draft):
    step = CreateGithubIssueStep(subcommand="feat", owner="test-owner", repo="test-repo")

    mock_response = MagicMock()
    mock_response.json.return_value = {"html_url": "https://github.com/test-owner/test-repo/issues/1"}
    mock_response.raise_for_status = MagicMock()

    with patch("src.workflow.steps.feat_issue.create_github_issue_step.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await step.execute(state_with_issue_draft)

    mock_client.post.assert_awaited_once()
    assert result.status == "success"
    assert "github_issue_url" in result.state_patch
    assert result.state_patch["github_issue_url"] == "https://github.com/test-owner/test-repo/issues/1"


async def test_github_payload_includes_title(state_with_issue_draft, feat_template):
    step = CreateGithubIssueStep(subcommand="feat", owner="test-owner", repo="test-repo")

    mock_response = MagicMock()
    mock_response.json.return_value = {"html_url": "https://github.com/test-owner/test-repo/issues/2"}
    mock_response.raise_for_status = MagicMock()

    with patch("src.workflow.steps.feat_issue.create_github_issue_step.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await step.execute(state_with_issue_draft)

    call_kwargs = mock_client.post.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert feat_template.issue_title in payload["title"]


async def test_step_control_signal_is_stop(state_with_issue_draft):
    step = CreateGithubIssueStep(subcommand="feat", owner="test-owner", repo="test-repo")

    mock_response = MagicMock()
    mock_response.json.return_value = {"html_url": "https://github.com/test-owner/test-repo/issues/3"}
    mock_response.raise_for_status = MagicMock()

    with patch("src.workflow.steps.feat_issue.create_github_issue_step.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await step.execute(state_with_issue_draft)

    assert result.control_signal == "stop"


async def test_step_raises_without_issue_draft():
    step = CreateGithubIssueStep(subcommand="feat", owner="test-owner", repo="test-repo")
    state = FeatIssueWorkflowState(user_message="test")
    with pytest.raises(ValueError, match="issue_draft is required"):
        await step.execute(state)


async def test_github_payload_includes_label(state_with_issue_draft):
    step = CreateGithubIssueStep(subcommand="feat", owner="test-owner", repo="test-repo")

    mock_response = MagicMock()
    mock_response.json.return_value = {"html_url": "https://github.com/test-owner/test-repo/issues/4"}
    mock_response.raise_for_status = MagicMock()

    with patch("src.workflow.steps.feat_issue.create_github_issue_step.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await step.execute(state_with_issue_draft)

    call_kwargs = mock_client.post.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert "feat" in payload["labels"]
