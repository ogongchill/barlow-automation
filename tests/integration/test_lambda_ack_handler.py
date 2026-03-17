"""Lambda Function URL 진입점 handler() 통합 테스트.

Lambda Function URL 이벤트 형식으로 handler()를 직접 호출하여
Bolt AsyncApp 디스패치 → 응답 변환 흐름을 검증한다.

외부 연동 mock:
  - SQS: src.controller.handler.slash._sqs
  - Slack client: slack_bolt.app.async_app.AsyncWebClient
  - App 인증: src.controller.lambda_ack._app (authorize= 기반으로 교체)
"""

import base64
import hashlib
import hmac
import inspect
import json
import time
import urllib.parse
from unittest.mock import patch

import pytest
from slack_bolt.async_app import AsyncApp
from slack_bolt.authorization import AuthorizeResult

from src.controller.router import register as _register_handlers

_SIGNING_SECRET = "test-signing-secret"  # tests/conftest.py SLACK_SIGNING_SECRET


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _function_url_event(body: str, *, bad_sig: bool = False) -> dict:
    """Lambda Function URL 형식 이벤트를 생성한다."""
    ts = str(int(time.time()))
    sig = "v0=" + hmac.new(
        _SIGNING_SECRET.encode(), f"v0:{ts}:{body}".encode(), hashlib.sha256
    ).hexdigest()
    if bad_sig:
        sig = "v0=" + "0" * 64
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": "/",
        "rawQueryString": "",
        "headers": {
            "content-type": "application/x-www-form-urlencoded",
            "x-slack-request-timestamp": ts,
            "x-slack-signature": sig,
        },
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "test-url-id",
            "http": {
                "method": "POST",
                "path": "/",
                "protocol": "HTTP/1.1",
                "sourceIp": "1.2.3.4",
                "userAgent": "Slackbot 1.0",
            },
            "requestId": "test-request-id",
            "routeKey": "$default",
            "stage": "$default",
            "timeEpoch": int(time.time() * 1000),
        },
        "body": body,
        "isBase64Encoded": False,
    }


def _slash_body(command: str) -> str:
    return (
        f"command={urllib.parse.quote(command)}"
        f"&trigger_id=trigger_id_1"
        f"&channel_id=C1&user_id=U1&text=&team_id=T1"
        f"&team_domain=testdomain"
        f"&response_url=https%3A%2F%2Fhooks.slack.com%2Fcommands%2Ftest"
    )


class MockContext:
    function_name = "barlow-ack"
    invoked_function_arn = (
        "arn:aws:lambda:ap-northeast-2:123456789012:function:barlow-ack"
    )


async def _authorize(**_) -> AuthorizeResult:
    """auth.test API 호출 없이 즉시 AuthorizeResult를 반환한다."""
    return AuthorizeResult(
        enterprise_id=None,
        team_id="T1",
        bot_token="xoxb-test",
        bot_id="B1",
        bot_user_id="U_BOT",
    )


@pytest.fixture()
def ack_handler_ctx(mock_sqs_client, mock_slack_client):
    """handler() 테스트 공통 컨텍스트.

    모듈 레벨 _app을 authorize= 기반 앱으로 교체하고
    per-request AsyncWebClient를 mock_slack_client로 대체한다.
    """
    test_app = AsyncApp(signing_secret=_SIGNING_SECRET, authorize=_authorize)
    _register_handlers(test_app)

    with (
        patch("src.controller.lambda_ack._app", test_app),
        patch("slack_bolt.app.async_app.AsyncWebClient", return_value=mock_slack_client),
    ):
        yield {"client": mock_slack_client, "sqs": mock_sqs_client}


# ── handler() 기본 검증 ──────────────────────────────────────────────────────

def test_handler_is_synchronous():
    """handler()는 코루틴 함수가 아닌 일반 함수여야 한다."""
    from src.controller.lambda_ack import handler
    assert not inspect.iscoroutinefunction(handler)


def test_handler_returns_dict_with_required_fields(ack_handler_ctx):
    """handler() 반환값은 statusCode, body, headers를 포함해야 한다."""
    from src.controller.lambda_ack import handler

    resp = handler(_function_url_event(_slash_body("/feat")), MockContext())

    assert "statusCode" in resp
    assert "body" in resp
    assert "headers" in resp


def test_valid_request_returns_200(ack_handler_ctx):
    """/feat 슬래시 커맨드 요청은 200을 반환해야 한다."""
    from src.controller.lambda_ack import handler

    resp = handler(_function_url_event(_slash_body("/feat")), MockContext())

    assert resp["statusCode"] == 200


def test_invalid_signature_returns_401(mock_sqs_client):
    """서명이 잘못된 요청은 401을 반환해야 한다 (Bolt 서명 검증 실패)."""
    from src.controller.lambda_ack import handler

    resp = handler(
        _function_url_event(_slash_body("/feat"), bad_sig=True), MockContext()
    )

    assert resp["statusCode"] == 401


def test_base64_encoded_body_is_decoded(ack_handler_ctx):
    """isBase64Encoded=True 이벤트의 body를 올바르게 디코딩해야 한다."""
    from src.controller.lambda_ack import handler

    raw_body = _slash_body("/feat")
    event = _function_url_event(raw_body)
    event["body"] = base64.b64encode(raw_body.encode()).decode()
    event["isBase64Encoded"] = True

    resp = handler(event, MockContext())

    assert resp["statusCode"] == 200


# ── _dispatch() 비동기 검증 ──────────────────────────────────────────────────

async def test_dispatch_slash_feat_opens_modal(ack_handler_ctx):
    """_dispatch()는 /feat 요청 처리 후 views_open을 호출해야 한다."""
    from src.controller.lambda_ack import _dispatch

    resp = await _dispatch(_function_url_event(_slash_body("/feat")))

    assert resp["statusCode"] == 200
    ack_handler_ctx["client"].views_open.assert_awaited_once()


async def test_dispatch_accept_action_sends_to_sqs(ack_handler_ctx):
    """_dispatch()는 issue_accept 액션을 accept 타입으로 SQS에 전송해야 한다."""
    from src.controller.lambda_ack import _dispatch

    payload = {
        "type": "block_actions",
        "team": {"id": "T1"},
        "user": {"id": "U1"},
        "channel": {"id": "C1"},
        "message": {"ts": "msg_ts_123", "text": "issue"},
        "trigger_id": "t1",
        "actions": [{"action_id": "issue_accept", "action_ts": "1.0"}],
    }
    body = "payload=" + urllib.parse.quote(json.dumps(payload))

    resp = await _dispatch(_function_url_event(body))

    assert resp["statusCode"] == 200
    ack_handler_ctx["sqs"].send.assert_called_once()
    msg = ack_handler_ctx["sqs"].send.call_args.args[0]
    assert msg["type"] == "accept"
