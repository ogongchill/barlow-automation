"""DM(Direct Message) 이벤트 핸들러."""

import logging

from slack_bolt.async_app import AsyncApp

from src.agent.base import IAgent
from src.session.manager import ISessionManager
from src.slack.handlers._reply import build_reply

logger = logging.getLogger(__name__)


def register(app: AsyncApp, agent: IAgent, session_manager: ISessionManager) -> None:
    """message 이벤트(DM)를 등록한다."""

    @app.event("message")
    async def handle_dm(event: dict, say) -> None:
        if event.get("channel_type") != "im" or event.get("bot_id") or event.get("subtype"):
            return
        # DM에서 @멘션으로 시작하는 메시지는 app_mention 핸들러가 처리
        text: str = event.get("text", "")
        if text.startswith("<@"):
            return

        user: str = event.get("user", "unknown")
        channel: str = event.get("channel", "unknown")

        session_key: str = f"{channel}:{user}"
        if not await session_manager.try_acquire(session_key):
            await say("이미 처리 중인 요청이 있습니다.")
            return

        logger.info("dm | agent=%s user=%s message=%r", agent.name, user, text)
        await say(f"<@{user}> 처리 중...")

        try:
            result = await agent.run(text)
            logger.info("dm | user=%s response_len=%d", user, len(result.output))
            await say(build_reply(None, result.output, result.usage.format()))
        except Exception:
            logger.exception("dm | user=%s 처리 중 오류 발생", user)
            await say("오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        finally:
            await session_manager.release(session_key)
