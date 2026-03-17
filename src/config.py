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
    slack_signing_secret: str
    slack_app_token: str        # Socket Mode용 (xapp-...)
    # anthropic_api_key: str
    github_token: str
    openai_api_key: str
    sqs_queue_url: str
    github_owner: str
    github_repo: str


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


def _parse_github_repo() -> tuple[str, str]:
    raw = _require("TARGET_REPO")
    # "https://github.com/owner/repo" 또는 "owner/repo" 형식 지원
    parts = raw.rstrip("/").split("/")
    return parts[-2], parts[-1]


_github_owner, _github_repo = _parse_github_repo()

config = Config(
    slack_bot_token=_require("SLACK_BOT_TOKEN"),
    slack_signing_secret=_require("SLACK_SIGNING_SECRET"),
    slack_app_token=os.getenv("SLACK_APP_TOKEN", ""),
    github_token=_require("GITHUB_TOKEN"),
    openai_api_key=_require("OPENAI_API_KEY"),
    sqs_queue_url=os.getenv("SQS_QUEUE_URL", ""),
    github_owner=_github_owner,
    github_repo=_github_repo,
)
