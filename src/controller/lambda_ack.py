"""Ack Lambda 진입점 — Lambda Function URL로 Slack 이벤트를 수신하고 ack한다."""

import asyncio
import base64
import logging

from src.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# Slack Bolt 초기화는 첫 Slack 이벤트 도달 시 한 번만 수행한다.
# EventBridge keep-warm ping은 Bolt 초기화 없이 즉시 반환하므로
# ping 자체가 초기화 비용을 유발하지 않는다.
_app = None


def _get_app():
    """Slack Bolt AsyncApp을 지연 초기화한다."""
    global _app
    if _app is not None:
        return _app

    from slack_bolt.async_app import AsyncApp  # noqa: PLC0415

    from src.controller.app import create_app
    from src.controller.handler import slash
    from src.controller.router import register
    from src.infrastructure.queue.sqs_publisher import SqsQueueSender
    from src.infrastructure.storage.dynamodb.active_session_store import (
        DynamoActiveSessionStore,
    )
    from src.infrastructure.storage.dynamodb.workflow_instance_store import (
        DynamoWorkflowInstanceStore,
    )

    slash.configure(
        workflow_repo=DynamoWorkflowInstanceStore(),
        active_session_repo=DynamoActiveSessionStore(),
        queue=SqsQueueSender(),
    )
    app: AsyncApp = create_app()
    register(app)
    _app = app
    return _app


async def _dispatch(event: dict) -> dict:
    """Lambda Function URL 이벤트를 Bolt AsyncApp으로 디스패치한다."""
    from slack_bolt.request.async_request import AsyncBoltRequest  # noqa: PLC0415

    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    headers = event.get("headers") or {}

    bolt_req = AsyncBoltRequest(body=body, headers=headers)
    bolt_resp = await _get_app().async_dispatch(bolt_req)

    return {
        "statusCode": bolt_resp.status,
        "body": bolt_resp.body or "",
        "headers": bolt_resp.first_headers(),
    }


def handler(event: dict, context) -> dict:
    """AWS Lambda Function URL 진입점.

    이벤트 유형별 분기:
    - EventBridge keep-warm ping: Bolt 우회, 즉시 200 반환
    - Slack HTTP 이벤트: Bolt AsyncApp으로 디스패치
    """
    if event.get("source") == "aws.events":
        logger.info("keep-warm ping received")
        return {"statusCode": 200, "body": "warm"}

    return asyncio.run(_dispatch(event))
