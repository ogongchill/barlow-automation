"""DM(Direct Message) 이벤트 핸들러."""

import logging

from slack_bolt.async_app import AsyncApp

from src.agent.base import IAgent
from src.slack.handlers._reply import build_reply

logger = logging.getLogger(__name__)


def register(app: AsyncApp, agent: IAgent) -> None:
    """message 이벤트(DM)를 등록한다."""

    @app.event("message")
    async def handle_dm(event: dict, say) -> None:
        if event.get("channel_type") != "im" or event.get("bot_id"):
            return

        user: str = event.get("user", "unknown")
        text: str = event.get("text", "")

        logger.info("dm | agent=%s user=%s message=%r", agent.name, user, text)
        await say(f"<@{user}> 처리 중...")

        try:
            response, usage = await agent.run(text)
            logger.info("dm | user=%s response_len=%d", user, len(response))
            await say(build_reply(None, response, usage.format()))
        except Exception:
            logger.exception("dm | user=%s 처리 중 오류 발생", user)
            await say("오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
