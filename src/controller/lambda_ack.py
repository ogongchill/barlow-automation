"""Ack Lambda 진입점 — Lambda Function URL로 Slack 이벤트를 수신하고 3초 이내 ack한다."""

import asyncio
import base64
import logging

from slack_bolt.async_app import AsyncApp
from slack_bolt.request.async_request import AsyncBoltRequest

from src.controller.app import create_app
from src.controller.handler import slash
from src.controller.router import register
from src.logging_config import setup_logging
from src.storage.request_dynamo_repository import DynamoPendingRepository
from src.storage.sqs_queue_sender import SqsQueueSender

setup_logging()
logger = logging.getLogger(__name__)

slash.configure(
    pending_repo=DynamoPendingRepository(),
    queue=SqsQueueSender(),
)

_app: AsyncApp = create_app()
register(_app)


async def _dispatch(event: dict) -> dict:
    """Lambda Function URL 이벤트를 Bolt AsyncApp으로 디스패치하고 응답 dict를 반환한다."""
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    headers = event.get("headers") or {}

    bolt_req = AsyncBoltRequest(body=body, headers=headers)
    bolt_resp = await _app.async_dispatch(bolt_req)

    return {
        "statusCode": bolt_resp.status,
        "body": bolt_resp.body or "",
        "headers": bolt_resp.first_headers(),
    }


def handler(event: dict, context) -> dict:
    """AWS Lambda Function URL 진입점."""
    return asyncio.run(_dispatch(event))
