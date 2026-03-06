"""Slash command 이벤트 핸들러."""

import logging

from slack_bolt.async_app import AsyncApp

from src.agent.base import IAgent
from src.slack.handlers._reply import build_reply

logger = logging.getLogger(__name__)

COMMAND_NAME = "/barlow"


def register(app: AsyncApp, agent: IAgent) -> None:
    """slash command를 등록한다."""

    @app.command(COMMAND_NAME)
    async def handle_slash(ack, command: dict, say) -> None:
        await ack()

        user: str = command.get("user_id", "unknown")
        channel: str = command.get("channel_id", "unknown")
        text: str = command.get("text", "").strip()

        logger.info(
            "slash | agent=%s user=%s channel=%s command=%s message=%r",
            agent.name, user, channel, COMMAND_NAME, text,
        )

        if not text:
            await say(f"<@{user}> 메시지를 입력해주세요. 예: `{COMMAND_NAME} 티켓 생성해줘`")
            return

        await say(f"<@{user}> 처리 중...")

        try:
            response, usage = await agent.run(text)
            logger.info("slash | user=%s response_len=%d", user, len(response))
            await say(build_reply(user, response, usage.format()))
        except Exception:
            logger.exception("slash | user=%s 처리 중 오류 발생", user)
            await say(f"<@{user}> 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
