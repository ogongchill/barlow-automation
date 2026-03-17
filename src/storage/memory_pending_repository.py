"""인메모리 IPendingRepository 구현체 — 로컬 개발용."""

from src.domain.pending import IPendingRepository, PendingRecord


class MemoryPendingRepository(IPendingRepository):
    """딕셔너리 기반 인메모리 IPendingRepository."""

    def __init__(self) -> None:
        self._store: dict[str, PendingRecord] = {}

    async def save(self, record: PendingRecord) -> None:
        self._store[record.pk] = record

    async def get(self, message_ts: str) -> PendingRecord | None:
        return self._store.get(message_ts)

    async def save_new_and_delete_old(
        self, new_record: PendingRecord, old_ts: str
    ) -> None:
        self._store[new_record.pk] = new_record
        self._store.pop(old_ts, None)

    async def delete(self, message_ts: str) -> None:
        self._store.pop(message_ts, None)
