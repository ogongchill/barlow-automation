"""MemoryActiveSessionStore -- 로컬 개발용 인메모리 활성 세션 저장소."""

from src.domain.common.ports.active_session import IActiveSessionRepository


class MemoryActiveSessionStore(IActiveSessionRepository):
    """channel_id + user_id 기준 활성 워크플로우 ID를 메모리에 저장한다."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def _key(self, channel_id: str, user_id: str) -> str:
        return f"{channel_id}#{user_id}"

    async def get_workflow_id(self, channel_id: str, user_id: str) -> str | None:
        return self._store.get(self._key(channel_id, user_id))

    async def set(self, channel_id: str, user_id: str, workflow_id: str) -> None:
        self._store[self._key(channel_id, user_id)] = workflow_id

    async def clear(self, channel_id: str, user_id: str) -> None:
        self._store.pop(self._key(channel_id, user_id), None)
