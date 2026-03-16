"""Pending 이슈 컨텍스트 도메인 모델 및 레포지토리 인터페이스."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.domain.issue_templates import (
    BaseIssueTemplate,
    FeatTemplate,
    RefactorTemplate,
    FixTemplate,
    Label,
)

PENDING_TTL_SECONDS = 60 * 60 * 24  # 24시간

_TEMPLATE_CLS: dict[str, type[BaseIssueTemplate]] = {
    Label.FEAT.value: FeatTemplate,
    Label.REFACTOR.value: RefactorTemplate,
    Label.FIX.value: FixTemplate,
}


@dataclass
class PendingRecord:
    """재요청/드롭 대기 중인 이슈 컨텍스트."""

    pk: str                      # Slack message_ts (이슈 결과 메시지)
    subcommand: str              # "feat" | "refactor" | "fix"
    user_id: str
    channel_id: str
    user_message: str            # Modal to_prompt() 결과
    inspector_output: str        # Inspector Agent 출력 (재요청 시 재사용)
    typed_output: BaseIssueTemplate
    ttl: int = field(default_factory=lambda: int(time.time()) + PENDING_TTL_SECONDS)

    def to_item(self) -> dict:
        """DynamoDB PutItem용 dict로 직렬화한다."""
        return {
            "pk": self.pk,
            "subcommand": self.subcommand,
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "user_message": self.user_message,
            "inspector_output": self.inspector_output,
            "typed_output": self.typed_output.model_dump_json(),
            "ttl": self.ttl,
        }

    @classmethod
    def from_item(cls, item: dict) -> "PendingRecord":
        """DynamoDB GetItem 응답을 PendingRecord로 역직렬화한다."""
        subcommand = item["subcommand"]
        template_cls = _TEMPLATE_CLS[subcommand]
        return cls(
            pk=item["pk"],
            subcommand=subcommand,
            user_id=item["user_id"],
            channel_id=item["channel_id"],
            user_message=item["user_message"],
            inspector_output=item["inspector_output"],
            typed_output=template_cls.model_validate_json(item["typed_output"]),
            ttl=int(item["ttl"]),
        )


class IPendingRepository(ABC):
    """Pending 이슈 컨텍스트 저장소 인터페이스."""

    @abstractmethod
    async def save(self, record: PendingRecord) -> None:
        """레코드를 저장한다."""
        ...

    @abstractmethod
    async def get(self, message_ts: str) -> PendingRecord | None:
        """message_ts로 레코드를 조회한다. 없으면 None 반환."""
        ...

    @abstractmethod
    async def save_new_and_delete_old(self, new_record: PendingRecord, old_ts: str) -> None:
        """새 레코드를 저장하고 기존 레코드를 원자적으로 삭제한다. (재요청 사이클용)"""
        ...

    @abstractmethod
    async def delete(self, message_ts: str) -> None:
        """레코드를 삭제한다. (수락 시)"""
        ...
