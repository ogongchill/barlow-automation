import asyncio
import logging
from dotenv import load_dotenv

load_dotenv(dotenv_path="default.env")
load_dotenv()  # .env가 있으면 덮어씀

from src.logging_config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

from src.slack.app import create_app
from src.session.manager import InMemorySessionManager
import src.agent.agents.open_ai_agents as openAiAgent

async def main() -> None:
    logger.info("Barlow automation bot starting (Socket Mode)...")

    agent = openAiAgent.create()
    logger.info("agent: %s", agent.name)

    session_manager = InMemorySessionManager()

    _, handler = create_app(agent, session_manager)
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
