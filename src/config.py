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
    anthropic_api_key: str
    github_token: str
    openai_api_key: str
    sqs_queue_url: str
    target_repo_owner: str
    target_repo_name: str


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


def _parse_target_repo() -> tuple[str, str]:
    raw = _require("TARGET_REPO")
    parts = raw.split("/", 1)
    if len(parts) != 2 or not all(parts):
        raise EnvironmentError(f"TARGET_REPO must be in 'owner/repo' format, got: {raw!r}")
    return parts[0], parts[1]


_repo_owner, _repo_name = _parse_target_repo()

config = Config(
    slack_bot_token=_require("SLACK_BOT_TOKEN"),
    slack_signing_secret=_require("SLACK_SIGNING_SECRET"),
    anthropic_api_key=_require("ANTHROPIC_API_KEY"),
    github_token=_require("GITHUB_TOKEN"),
    openai_api_key=_require("OPENAI_API_KEY"),
    sqs_queue_url=_require("SQS_QUEUE_URL"),
    target_repo_owner=_repo_owner,
    target_repo_name=_repo_name,
)
