"""storage 레이어 상수 및 재export."""

# PendingRecord는 domain 레이어에 위치한다.
# storage 모듈은 domain 인터페이스를 구현하는 구체 클래스만 포함한다.
from src.domain.pending import PendingRecord, PENDING_TTL_SECONDS

IDEMPOTENCY_TTL_SECONDS = 60 * 60  # 1시간

__all__ = ["PendingRecord", "PENDING_TTL_SECONDS", "IDEMPOTENCY_TTL_SECONDS"]
