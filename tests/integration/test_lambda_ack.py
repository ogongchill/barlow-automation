"""Ack Lambda 통합 테스트 — Slack 이벤트 → SQS/views_open 흐름 검증.

외부 연동 mock:
  - SQS: src.controller.handler.slash._sqs
  - DynamoDB: src.controller.handler.slash._pending_repo
  - Slack client: app._client
"""

import json
import urllib.parse
from unittest.mock import AsyncMock, patch

import pytest
from slack_bolt.async_app import AsyncApp
from slack_bolt.request.async_request import AsyncBoltRequest

from src.controller.handler.slash import register


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _slash_body(command: str, channel_id: str = "C1", user_id: str = "U1") -> str:
    return (
        f"command={urllib.parse.quote(command)}"
        f"&trigger_id=trigger_id_1"
        f"&channel_id={channel_id}"
        f"&user_id={user_id}"
        f"&text="
        f"&team_id=T1"
        f"&team_domain=testdomain"
        f"&response_url=https%3A%2F%2Fhooks.slack.com%2Fcommands%2Ftest"
    )


def _view_body(callback_id: str, values: dict, private_metadata: str = "") -> str:
    payload = {
        "type": "view_submission",
        "team": {"id": "T1"},
        "user": {"id": "U1"},
        "view": {
            "id": "view_id_1",
            "type": "modal",
            "callback_id": callback_id,
            "private_metadata": private_metadata,
            "state": {"values": values},
        },
    }
    return "payload=" + urllib.parse.quote(json.dumps(payload))


def _action_body(action_id: str, message_ts: str = "msg_ts_123", channel_id: str = "C1") -> str:
    payload = {
        "type": "block_actions",
        "team": {"id": "T1"},
        "user": {"id": "U1"},
        "channel": {"id": channel_id},
        "message": {"ts": message_ts, "text": "issue"},
        "trigger_id": "trigger_id_1",
        "actions": [{"action_id": action_id, "action_ts": "123.456"}],
    }
    return "payload=" + urllib.parse.quote(json.dumps(payload))


def _req(body: str, content_type: str = "application/x-www-form-urlencoded") -> AsyncBoltRequest:
    return AsyncBoltRequest(body=body, headers={"content-type": content_type})


@pytest.fixture()
def ack_app(mock_sqs_client, mock_slack_client):
    """의존성이 mock된 AsyncApp."""
    app = AsyncApp(token="xoxb-test", signing_secret=None)
    app._client = mock_slack_client
    register(app)
    return app


# ── Slash commands → views_open ───────────────────────────────────────────────

async def test_slash_feat_opens_modal(ack_app, mock_slack_client):
    await ack_app.async_dispatch(_req(_slash_body("/feat")))
    mock_slack_client.views_open.assert_awaited_once()
    view = mock_slack_client.views_open.call_args.kwargs["view"]
    assert view["callback_id"] == "feat_submit"


async def test_slash_refactor_opens_modal(ack_app, mock_slack_client):
    await ack_app.async_dispatch(_req(_slash_body("/refactor")))
    mock_slack_client.views_open.assert_awaited_once()
    view = mock_slack_client.views_open.call_args.kwargs["view"]
    assert view["callback_id"] == "refactor_submit"


async def test_slash_fix_opens_modal(ack_app, mock_slack_client):
    await ack_app.async_dispatch(_req(_slash_body("/fix")))
    mock_slack_client.views_open.assert_awaited_once()
    view = mock_slack_client.views_open.call_args.kwargs["view"]
    assert view["callback_id"] == "fix_submit"


# ── view_submission → SQS pipeline_start ─────────────────────────────────────

def _feat_values() -> dict:
    return {
        "feature_name":        {"input": {"value": "즐겨찾기"}},
        "background":          {"input": {"value": "자주 방문하는 페이지"}},
        "features":            {"input": {"value": "추가\n조회"}},
        "constraints":         {"input": {"value": "로그인 필요"}},
        "design_requirements": {"input": {"value": None}},
    }


async def test_feat_submit_sends_pipeline_start_to_sqs(ack_app, mock_sqs_client):
    body = _view_body("feat_submit", _feat_values(), private_metadata=json.dumps({"channel_id": "C1"}))
    await ack_app.async_dispatch(_req(body))

    mock_sqs_client.send_message.assert_called_once()
    payload = json.loads(mock_sqs_client.send_message.call_args.kwargs["MessageBody"])
    assert payload["type"] == "pipeline_start"
    assert payload["subcommand"] == "feat"
    assert payload["channel_id"] == "C1"
    assert payload["user_id"] == "U1"
    assert "[feat]" in payload["user_message"]
    assert "dedup_id" in payload


async def test_refactor_submit_sends_pipeline_start(ack_app, mock_sqs_client):
    values = {
        "target_name": {"input": {"value": "SessionManager"}},
        "background":  {"input": {"value": "책임 과다"}},
        "as_is":       {"input": {"value": "직접 참조"}},
        "to_be":       {"input": {"value": "인터페이스 주입"}},
        "constraints": {"input": {"value": None}},
    }
    body = _view_body("refactor_submit", values, private_metadata=json.dumps({"channel_id": "C1"}))
    await ack_app.async_dispatch(_req(body))

    payload = json.loads(mock_sqs_client.send_message.call_args.kwargs["MessageBody"])
    assert payload["type"] == "pipeline_start"
    assert payload["subcommand"] == "refactor"


async def test_fix_submit_sends_pipeline_start(ack_app, mock_sqs_client):
    values = {
        "bug_title":     {"input": {"value": "로그인 NPE"}},
        "symptom":       {"input": {"value": "null 참조"}},
        "reproduction":  {"input": {"value": "로그인 시"}},
        "expected":      {"input": {"value": "정상 처리"}},
        "related_areas": {"input": {"value": None}},
    }
    body = _view_body("fix_submit", values, private_metadata=json.dumps({"channel_id": "C1"}))
    await ack_app.async_dispatch(_req(body))

    payload = json.loads(mock_sqs_client.send_message.call_args.kwargs["MessageBody"])
    assert payload["type"] == "pipeline_start"
    assert payload["subcommand"] == "fix"


# ── Block Actions ─────────────────────────────────────────────────────────────

async def test_issue_accept_sends_accept_to_sqs(ack_app, mock_sqs_client):
    await ack_app.async_dispatch(_req(_action_body("issue_accept")))

    payload = json.loads(mock_sqs_client.send_message.call_args.kwargs["MessageBody"])
    assert payload["type"] == "accept"
    assert payload["message_ts"] == "msg_ts_123"
    assert payload["channel_id"] == "C1"


async def test_issue_reject_opens_reject_modal(ack_app, mock_slack_client):
    await ack_app.async_dispatch(_req(_action_body("issue_reject")))

    mock_slack_client.views_open.assert_awaited_once()
    view = mock_slack_client.views_open.call_args.kwargs["view"]
    assert view["callback_id"] == "reject_submit"
    meta = json.loads(view["private_metadata"])
    assert meta["message_ts"] == "msg_ts_123"
    assert meta["channel_id"] == "C1"


async def test_issue_drop_opens_drop_modal(ack_app, mock_slack_client, mock_pending_repo):
    with patch("src.controller.handler.slash._pending_repo", mock_pending_repo):
        await ack_app.async_dispatch(_req(_action_body("issue_drop")))

    mock_pending_repo.get.assert_awaited_once_with("msg_ts_123")
    mock_slack_client.views_open.assert_awaited_once()
    view = mock_slack_client.views_open.call_args.kwargs["view"]
    assert view["callback_id"] == "drop_submit"


async def test_issue_drop_no_record_skips_modal(ack_app, mock_slack_client):
    empty_repo = AsyncMock()
    empty_repo.get = AsyncMock(return_value=None)
    with patch("src.controller.handler.slash._pending_repo", empty_repo):
        await ack_app.async_dispatch(_req(_action_body("issue_drop")))

    mock_slack_client.views_open.assert_not_awaited()


# ── Reject/Drop submit → SQS ──────────────────────────────────────────────────

async def test_reject_submit_sends_reject_to_sqs(ack_app, mock_sqs_client):
    meta = json.dumps({"message_ts": "ts1", "channel_id": "C1", "user_id": "U1"})
    values = {"additional_requirements": {"input": {"value": "성능 개선 추가"}}}
    body = _view_body("reject_submit", values, private_metadata=meta)
    await ack_app.async_dispatch(_req(body))

    payload = json.loads(mock_sqs_client.send_message.call_args.kwargs["MessageBody"])
    assert payload["type"] == "reject"
    assert payload["message_ts"] == "ts1"
    assert payload["additional_requirements"] == "성능 개선 추가"


async def test_reject_submit_none_when_no_additional(ack_app, mock_sqs_client):
    meta = json.dumps({"message_ts": "ts1", "channel_id": "C1", "user_id": "U1"})
    values = {"additional_requirements": {"input": {"value": None}}}
    body = _view_body("reject_submit", values, private_metadata=meta)
    await ack_app.async_dispatch(_req(body))

    payload = json.loads(mock_sqs_client.send_message.call_args.kwargs["MessageBody"])
    assert payload["additional_requirements"] is None


async def test_drop_submit_sends_drop_restart_to_sqs(ack_app, mock_sqs_client):
    meta = json.dumps({"message_ts": "ts1", "channel_id": "C1", "user_id": "U1"})
    values = {"drop_selection": {"items": {"selected_options": [
        {"value": "new_features::0"},
        {"value": "domain_rules::0"},
    ]}}}
    body = _view_body("drop_submit", values, private_metadata=meta)
    await ack_app.async_dispatch(_req(body))

    payload = json.loads(mock_sqs_client.send_message.call_args.kwargs["MessageBody"])
    assert payload["type"] == "drop_restart"
    assert payload["message_ts"] == "ts1"
    assert set(payload["dropped_ids"]) == {"new_features::0", "domain_rules::0"}


async def test_drop_submit_empty_selection(ack_app, mock_sqs_client):
    meta = json.dumps({"message_ts": "ts1", "channel_id": "C1", "user_id": "U1"})
    values = {"drop_selection": {"items": {"selected_options": []}}}
    body = _view_body("drop_submit", values, private_metadata=meta)
    await ack_app.async_dispatch(_req(body))

    payload = json.loads(mock_sqs_client.send_message.call_args.kwargs["MessageBody"])
    assert payload["dropped_ids"] == []
