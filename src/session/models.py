"""세션 데이터 구조 정의."""

from dataclasses import dataclass
from enum import Enum


class SessionStatus(Enum):
    """세션의 현재 상태."""

    IDLE = "idle"
    RUNNING = "running"


@dataclass
class Session:
    """단일 세션을 나타내는 데이터 구조.

    key 형식: "{channel_id}:{user_id}"
    """

    key: str
    status: SessionStatus = SessionStatus.IDLE
