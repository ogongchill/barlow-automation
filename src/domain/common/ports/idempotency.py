"""Idempotency 도메인 인터페이스 -- LLM 중복 호출 방지."""

from abc import ABC, abstractmethod


class IIdempotencyRepository(ABC):
    """Idempotency 키 저장소 인터페이스."""

    @abstractmethod
    async def try_acquire(self, message_ts: str) -> bool:
        """
        Idempotency 키 획득을 시도한다.

        최초 호출이면 PROCESSING 상태로 기록하고 True 반환.
        이미 존재하면 (중복 호출) False 반환.
        """
        ...

    @abstractmethod
    async def mark_done(self, message_ts: str) -> None:
        """처리 완료 상태로 갱신한다."""
        ...
