"""IQueueSender 인터페이스 — SQS 메시지 전송 추상화."""

from abc import ABC, abstractmethod


class IQueueSender(ABC):
    """SQS(또는 로컬 대체) 메시지 전송 인터페이스."""

    @abstractmethod
    def send(self, message: dict) -> None:
        """메시지를 큐에 전송한다."""
        ...
