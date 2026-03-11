import logging
from slack_bolt.async_app import AsyncApp
from src.session.manager import ISessionManager
from src.slack.handlers._reply import build_reply
from src.agent.agents.agent_factory import OpenAiAgentFactory

logger = logging.getLogger(__name__)


def register(
    app: AsyncApp,
    session_manager: ISessionManager
) -> None:

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
            "mention | user=%s channel=%s message=%r",
        )
        await say(f"<@{user}> 처리 중...")
        plannerAgent = OpenAiAgentFactory.file_tree_insepctor()
        issueAgent = OpenAiAgentFactory.feat_issue_gen()
        try:
            result = await plannerAgent.run(user_message)
            logger.info("mention | agent got message to user=%s", user)
            await say(build_reply(user, "파일 목록을 확인했습니다. 계속 진행합니다...", result.usage.format()))
            issue = await issueAgent.run(result.output)
            logger.info("mention | generating issues,,,,,")
            await say(build_reply(user, issue.output, issue.usage.format()))
        except Exception:
            logger.exception("mention | user=%s 처리 중 오류 발생", user)
            await say(f"<@{user}> 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        finally:
            await session_manager.release(session_key)
