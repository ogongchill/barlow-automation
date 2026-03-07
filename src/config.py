import os
import sys
from dataclasses import dataclass
from enum import Enum


class OsType(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"


@dataclass
class Config:
    slack_bot_token: str
    slack_app_token: str
    slack_signing_secret: str
    anthropic_api_key: str
    agent_model: str
    agent_max_tokens: int
    github_token: str
    openai_api_key: str
    os_type: OsType


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return value


def _detect_os_type() -> OsType:
    raw = os.getenv("OS_TYPE")
    if raw:
        return OsType(raw.lower())
    return OsType.WINDOWS if sys.platform == "win32" else OsType.LINUX


config = Config(
    slack_bot_token=_require("SLACK_BOT_TOKEN"),
    slack_app_token=_require("SLACK_APP_TOKEN"),
    slack_signing_secret=_require("SLACK_SIGNING_SECRET"),
    anthropic_api_key=_require("ANTHROPIC_API_KEY"),
    agent_model=os.getenv("AGENT_MODEL", "claude-sonnet-4-6"),
    agent_max_tokens=int(os.getenv("AGENT_MAX_TOKENS", "8096")),
    github_token=_require("GITHUB_TOKEN"),
    openai_api_key=_require("OPENAI_API_KEY"),
    os_type=_detect_os_type(),
)
