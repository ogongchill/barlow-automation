"""세션 매니저 -- asyncio.Lock 기반 동시성 제어."""

import asyncio
from abc import ABC, abstractmethod

from src.session.models import Session, SessionStatus


class ISessionManager(ABC):
    """세션 관리 인터페이스.

    구체 구현(InMemory, Redis 등)은 이 인터페이스를 구현하며,
    외부 모듈은 ISessionManager에만 의존한다.
    """

    @abstractmethod
    async def try_acquire(self, key: str) -> bool:
        """세션 획득을 시도한다. 이미 RUNNING이면 False를 반환한다."""
        ...

    @abstractmethod
    async def release(self, key: str) -> None:
        """세션을 해제하여 IDLE 상태로 되돌린다."""
        ...

    @abstractmethod
    async def is_running(self, key: str) -> bool:
        """해당 키의 세션이 현재 RUNNING 상태인지 조회한다."""
        ...


class InMemorySessionManager(ISessionManager):
    """asyncio.Lock 기반 인메모리 세션 매니저.

    단일 프로세스 환경에서 동일 사용자의 동시 요청을 방지한다.
    """

    def __init__(self) -> None:
        self._lock: asyncio.Lock = asyncio.Lock()
        self._sessions: dict[str, Session] = {}

    async def try_acquire(self, key: str) -> bool:
        """세션 획득을 시도한다. 이미 RUNNING이면 False를 반환한다."""
        async with self._lock:
            session = self._sessions.get(key)
            if session and session.status == SessionStatus.RUNNING:
                return False
            self._sessions[key] = Session(key=key, status=SessionStatus.RUNNING)
            return True

    async def release(self, key: str) -> None:
        """세션을 해제하여 IDLE 상태로 되돌린다."""
        async with self._lock:
            session = self._sessions.get(key)
            if session:
                session.status = SessionStatus.IDLE

    async def is_running(self, key: str) -> bool:
        """해당 키의 세션이 현재 RUNNING 상태인지 조회한다."""
        async with self._lock:
            session = self._sessions.get(key)
            return session is not None and session.status == SessionStatus.RUNNING
