"""DM 메시지 핸들러 — 슬래시 커맨드 안내."""

from slack_bolt.async_app import AsyncApp


def register(app: AsyncApp) -> None:

    @app.event("message")
    async def handle_message(ack, say):
        await ack()
        await say("/feat, /refactor, /fix 슬래시 커맨드를 사용해 주세요.")
