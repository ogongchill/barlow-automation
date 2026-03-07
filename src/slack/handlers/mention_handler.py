"""@mention 이벤트 핸들러."""

import logging

from slack_bolt.async_app import AsyncApp

from src.agent.base import IAgent
from src.session.manager import ISessionManager
from src.slack.handlers._reply import build_reply

logger = logging.getLogger(__name__)


def register(app: AsyncApp, agent: IAgent, session_manager: ISessionManager) -> None:
    """app_mention 이벤트를 등록한다."""

    @app.event("app_mention")
    async def handle_mention(event: dict, say) -> None:
        user: str = event.get("user", "unknown")
        channel: str = event.get("channel", "unknown")
        text: str = event.get("text", "")
        user_message: str = text.split(">", 1)[-1].strip()

        session_key: str = f"{channel}:{user}"
        if not await session_manager.try_acquire(session_key):
            await say(f"<@{user}> 이미 처리 중인 요청이 있습니다.")
            return

        logger.info(
            "mention | agent=%s user=%s channel=%s message=%r",
            agent.name, user, channel, user_message,
        )
        await say(f"<@{user}> 처리 중...")

        try:
            result = await agent.run(user_message)
            logger.info("mention | user=%s response_len=%d", user, len(result.output))
            await say(build_reply(user, result.output, result.usage.format()))
        except Exception:
            logger.exception("mention | user=%s 처리 중 오류 발생", user)
            await say(f"<@{user}> 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        finally:
            await session_manager.release(session_key)
