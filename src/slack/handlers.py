import logging

from slack_bolt.async_app import AsyncApp

from src.agent.base import IAgent

logger = logging.getLogger(__name__)


def _build_reply(user: str | None, response: str, usage_text: str) -> str:
    base = f"<@{user}> {response}" if user else response
    if not usage_text:
        return base
    return f"{base}\n\n```{usage_text}```"


def register_handlers(app: AsyncApp, agent: IAgent) -> None:
    @app.event("app_mention")
    async def handle_mention(event: dict, say) -> None:
        user = event.get("user", "unknown")
        channel = event.get("channel", "unknown")
        text = event.get("text", "")
        user_message = text.split(">", 1)[-1].strip()

        logger.info("mention | agent=%s user=%s channel=%s message=%r", agent.name, user, channel, user_message)
        await say(f"<@{user}> 처리 중...")

        try:
            response, usage = await agent.run(user_message)
            logger.info("mention | user=%s response_len=%d", user, len(response))
            await say(_build_reply(user, response, usage.format()))
        except Exception:
            logger.exception("mention | user=%s 처리 중 오류 발생", user)
            await say(f"<@{user}> 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")

    @app.event("message")
    async def handle_dm(event: dict, say) -> None:
        if event.get("channel_type") != "im" or event.get("bot_id"):
            return

        user = event.get("user", "unknown")
        text = event.get("text", "")

        logger.info("dm | agent=%s user=%s message=%r", agent.name, user, text)
        await say(f"<@{user}> 처리 중...")

        try:
            response, usage = await agent.run(text)
            logger.info("dm | user=%s response_len=%d", user, len(response))
            await say(_build_reply(None, response, usage.format()))
        except Exception:
            logger.exception("dm | user=%s 처리 중 오류 발생", user)
            await say("오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
