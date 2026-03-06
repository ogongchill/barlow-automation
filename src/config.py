import os
from dataclasses import dataclass


@dataclass
class Config:
    slack_bot_token: str
    slack_app_token: str
    slack_signing_secret: str
    anthropic_api_key: str
    agent_model: str
    agent_max_tokens: int
    github_token: str | None

def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return value

config = Config(
    slack_bot_token=_require("SLACK_BOT_TOKEN"),
    slack_app_token=_require("SLACK_APP_TOKEN"),
    slack_signing_secret=_require("SLACK_SIGNING_SECRET"),
    anthropic_api_key=_require("ANTHROPIC_API_KEY"),
    agent_model=os.getenv("AGENT_MODEL", "claude-sonnet-4-6"),
    agent_max_tokens=int(os.getenv("AGENT_MAX_TOKENS", "8096")),
    github_token=os.getenv("GITHUB_TOKEN"),
)
