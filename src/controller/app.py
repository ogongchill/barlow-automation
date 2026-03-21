"""Slack AsyncApp 팩토리 — HTTP 모드 (Lambda 전용)."""

from slack_bolt.async_app import AsyncApp

from src.config import config


def create_app() -> AsyncApp:
    return AsyncApp(
        token=config.slack_bot_token,
        signing_secret=config.slack_signing_secret,
        process_before_response=True,
    )
