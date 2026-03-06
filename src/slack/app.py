from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from src.agent.base import IAgent
from src.config import config
from src.slack.event_router import register_routes


def create_app(agent: IAgent) -> tuple[AsyncApp, AsyncSocketModeHandler]:
    app = AsyncApp(
        token=config.slack_bot_token,
        signing_secret=config.slack_signing_secret,
    )

    register_routes(app, agent)

    handler = AsyncSocketModeHandler(app, config.slack_app_token)
    return app, handler
