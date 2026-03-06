"""AsyncApp 팩토리 -- Slack Bolt 앱 인스턴스를 생성한다."""

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from src.agent.base import IAgent
from src.config import config
from src.session.manager import ISessionManager
from src.slack.event_router import register_routes


def create_app(
    agent: IAgent,
    session_manager: ISessionManager,
) -> tuple[AsyncApp, AsyncSocketModeHandler]:
    """Slack AsyncApp과 SocketModeHandler를 생성하여 반환한다."""
    app = AsyncApp(
        token=config.slack_bot_token,
        signing_secret=config.slack_signing_secret,
    )

    register_routes(app, agent, session_manager)

    handler = AsyncSocketModeHandler(app, config.slack_app_token)
    return app, handler
