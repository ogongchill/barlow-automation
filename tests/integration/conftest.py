"""Integration test fixtures -- mocks for SQS, Slack, repositories, services."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.feat.models.issue import FeatTemplate
from src.domain.common.models.lifecycle import WorkflowStatus
from src.domain.common.models.workflow_instance import WorkflowInstance
from src.domain.feat.models.state import FeatIssueWorkflowState


def _default_feat_template() -> FeatTemplate:
    return FeatTemplate(
        issue_title="[FEAT] Test feature",
        about="Test about.",
        goal="테스트 목표.",
        new_features=["feature A", "feature B"],
        domain_rules=["rule 1"],
        additional_info="",
    )


def _default_workflow_instance() -> WorkflowInstance:
    state = FeatIssueWorkflowState(
        user_message="[feat] Test\n\n배경: test\n\n기능:\n- A",
        bc_candidates="bc finder context",
        issue_draft=_default_feat_template().model_dump_json(),
    )
    now = int(time.time())
    return WorkflowInstance(
        workflow_id="wf-test-123",
        workflow_type="feat_issue",
        status=WorkflowStatus.WAITING,
        current_step="wait_confirmation",
        state=state,
        pending_action_token="token-abc",
        slack_channel_id="C1",
        slack_user_id="U1",
        slack_message_ts="msg_ts_123",
        created_at=now,
        ttl=now + 86400,
    )


@pytest.fixture()
def mock_sqs_client():
    with patch("src.controller.handler.slash._queue") as mock_queue:
        mock_queue.send = MagicMock()
        yield mock_queue


@pytest.fixture()
def mock_slack_client():
    client = AsyncMock()
    client.auth_test = AsyncMock(
        return_value={"ok": True, "bot_id": "B1", "user_id": "U_BOT", "team_id": "T1"}
    )
    client.views_open = AsyncMock(return_value={"ok": True})
    client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "new_ts"})
    client.chat_update = AsyncMock(return_value={"ok": True})
    return client


@pytest.fixture()
def mock_workflow_repo():
    repo = AsyncMock()
    repo.save = AsyncMock()
    repo.get = AsyncMock(return_value=_default_workflow_instance())
    return repo


@pytest.fixture()
def mock_idempotency_repo():
    repo = AsyncMock()
    repo.try_acquire = AsyncMock(return_value=True)
    repo.mark_done = AsyncMock()
    return repo
