"""Integration test fixtures -- mocks for SQS, Slack, repositories, services."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent.usage import AgentUsage
from src.domain.issue_templates import FeatTemplate
from src.domain.pending import PendingRecord


def _default_feat_template() -> FeatTemplate:
    return FeatTemplate(
        issue_title="[FEAT] Test feature",
        about="Test about.",
        new_features=["feature A", "feature B"],
        domain_rules=["rule 1"],
        domain_constraints=["constraint 1"],
    )


def _default_pending_record() -> PendingRecord:
    return PendingRecord(
        pk="msg_ts_123",
        subcommand="feat",
        user_id="U1",
        channel_id="C1",
        user_message="[feat] Test\n\n배경: test\n\n기능:\n- A",
        inspector_output="inspector context",
        typed_output=_default_feat_template(),
    )


@pytest.fixture()
def mock_sqs_client():
    with patch("src.controller.handler.slash._sqs") as mock_sqs:
        mock_sqs.send_message = MagicMock()
        yield mock_sqs


@pytest.fixture()
def mock_slack_client():
    client = AsyncMock()
    client.auth_test = AsyncMock(return_value={"ok": True, "bot_id": "B1", "user_id": "U_BOT", "team_id": "T1"})
    client.views_open = AsyncMock(return_value={"ok": True})
    client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "new_ts"})
    client.chat_update = AsyncMock(return_value={"ok": True})
    return client


@pytest.fixture()
def mock_pending_repo():
    repo = AsyncMock()
    repo.save = AsyncMock()
    repo.get = AsyncMock(return_value=_default_pending_record())
    repo.delete = AsyncMock()
    repo.save_new_and_delete_old = AsyncMock()
    return repo


@pytest.fixture()
def mock_idempotency_repo():
    repo = AsyncMock()
    repo.try_acquire = AsyncMock(return_value=True)
    repo.mark_done = AsyncMock()
    return repo


@pytest.fixture()
def mock_services():
    with (
        patch("src.lambda_worker.run_read_planner", new_callable=AsyncMock) as mock_planner,
        patch("src.lambda_worker.run_issue_generator", new_callable=AsyncMock) as mock_issue_gen,
        patch("src.lambda_worker.run_re_issue_generator", new_callable=AsyncMock) as mock_reissue_gen,
        patch("src.lambda_worker.run_issue_creator", new_callable=AsyncMock, create=True) as mock_issue_creator,
    ):
        mock_planner.return_value = ("inspector output text", AgentUsage(input_tokens=100, output_tokens=50))
        mock_issue_gen.return_value = (_default_feat_template(), AgentUsage(input_tokens=50, output_tokens=30))
        mock_reissue_gen.return_value = (_default_feat_template(), AgentUsage(input_tokens=40, output_tokens=20))
        mock_issue_creator.return_value = "https://github.com/ogongchill/barlow/issues/42"
        yield {
            "run_read_planner": mock_planner,
            "run_issue_generator": mock_issue_gen,
            "run_re_issue_generator": mock_reissue_gen,
            "run_issue_creator": mock_issue_creator,
        }
