"""인메모리 IIdempotencyRepository 구현체 — 로컬 개발용."""

from src.domain.idempotency import IIdempotencyRepository


class MemoryIdempotencyRepository(IIdempotencyRepository):
    """set 기반 인메모리 IIdempotencyRepository."""

    def __init__(self) -> None:
        self._acquired: set[str] = set()

    async def try_acquire(self, message_ts: str) -> bool:
        if message_ts in self._acquired:
            return False
        self._acquired.add(message_ts)
        return True

    async def mark_done(self, message_ts: str) -> None:
        pass  # 인메모리에서는 상태 구분 불필요
