"""이벤트 핸들러를 AsyncApp에 등록한다."""

from slack_bolt.async_app import AsyncApp

from src.controller.handler import slash, mention, message


def register(app: AsyncApp) -> None:
    slash.register(app)
    mention.register(app)
    message.register(app)
