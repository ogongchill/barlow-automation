import asyncio
import logging
from dotenv import load_dotenv

load_dotenv(dotenv_path="default.env")
load_dotenv()  # .env가 있으면 덮어씀

from src.logging_config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

from src.config import config
from src.slack.app import create_app
from src.agent.agents import github, general


async def main() -> None:
    logger.info("Barlow automation bot starting (Socket Mode)...")
    logger.info("GitHub MCP: %s", "enabled" if config.github_token else "disabled")

    agent = github.create() if config.github_token else general.create()
    logger.info("agent: %s", agent.name)

    _, handler = create_app(agent)
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
