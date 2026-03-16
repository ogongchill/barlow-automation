"""Ack Lambda 진입점 — Slack HTTP 요청을 3초 안에 ack한다."""

from slack_bolt.adapter.aws_lambda.async_handler import AsyncSlackRequestHandler

from src.controller.app import create_app
from src.controller.router import register
from src.logging_config import setup_logging

setup_logging()

_app = create_app()
register(_app)

_handler = AsyncSlackRequestHandler(_app)


async def handler(event, context):
    """AWS Lambda entry point — Slack Events / Actions / Views."""
    return await _handler.handle(event, context)
