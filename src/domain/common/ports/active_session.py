"""IActiveSessionRepository -- 채널+사용자 단위 활성 워크플로우 추적 인터페이스."""

from abc import ABC, abstractmethod


class IActiveSessionRepository(ABC):
    """채널+사용자 기준으로 활성 워크플로우 ID를 관리한다."""

    @abstractmethod
    async def get_workflow_id(self, channel_id: str, user_id: str) -> str | None:
        """활성 워크플로우 ID를 반환한다. 없으면 None."""
        ...

    @abstractmethod
    async def set(self, channel_id: str, user_id: str, workflow_id: str) -> None:
        """활성 워크플로우 ID를 저장한다."""
        ...

    @abstractmethod
    async def clear(self, channel_id: str, user_id: str) -> None:
        """활성 워크플로우 기록을 삭제한다."""
        ...
