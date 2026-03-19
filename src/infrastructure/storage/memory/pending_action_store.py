"""Pending Action 인메모리 저장소 -- 로컬 개발용."""

from src.domain.common.ports.idempotency import IIdempotencyRepository


class MemoryPendingActionStore(IIdempotencyRepository):
    """set 기반 인메모리 멱등성 저장소."""

    def __init__(self) -> None:
        self._acquired: set[str] = set()

    async def try_acquire(self, key: str) -> bool:
        if key in self._acquired:
            return False
        self._acquired.add(key)
        return True

    async def mark_done(self, key: str) -> None:
        pass  # 인메모리에서는 상태 구분 불필요
