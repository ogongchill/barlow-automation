import asyncio
import logging
from dotenv import load_dotenv

load_dotenv(dotenv_path="default.env")
load_dotenv()  # .env가 있으면 덮어씀

from src.slack.app import create_app
from src.session.manager import InMemorySessionManager
from src.logging_config import setup_logging
from src.agent.agents.github import GitHubMCPFactory

setup_logging()
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("bot starting (Socket Mode)...")

    await GitHubMCPFactory.connect()
    logger.info("GitHub MCP servers connected.")

    try:
        session_manager = InMemorySessionManager()
        _, handler = create_app(session_manager)
        await handler.start_async()
    finally:
        await GitHubMCPFactory.disconnect()
        logger.info("GitHub MCP servers disconnected.")


if __name__ == "__main__":
    asyncio.run(main())
