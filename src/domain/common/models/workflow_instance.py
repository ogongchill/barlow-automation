"""Workflow 인스턴스 및 저장소 인터페이스."""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from src.domain.common.models.lifecycle import WorkflowStatus

WORKFLOW_TTL_SECONDS = 60 * 60 * 24  # 24시간

# workflow_type -> state class 매핑 레지스트리.
# 각 feature 모듈이 register_state_cls()로 자신의 state class를 등록한다.
_STATE_CLS: dict[str, type] = {}


def register_state_cls(workflow_type: str, cls: type) -> None:
    """feature 모듈이 자신의 state class를 등록한다."""
    _STATE_CLS[workflow_type] = cls


@dataclass
class WorkflowInstance:
    workflow_id: str
    workflow_type: str
    status: WorkflowStatus
    current_step: str
    state: Any
    pending_action_token: str | None
    slack_channel_id: str
    slack_user_id: str
    slack_message_ts: str | None
    created_at: int
    ttl: int

    @classmethod
    def create(
        cls,
        workflow_type: str,
        slack_channel_id: str,
        slack_user_id: str,
        user_message: str,
        first_step: str = "find_relevant_bc",
    ) -> WorkflowInstance:
        state_cls = _STATE_CLS.get(workflow_type)
        if state_cls is None:
            raise KeyError(f"No state class registered for workflow_type={workflow_type}")
        now = int(time.time())
        return cls(
            workflow_id=str(uuid.uuid4()),
            workflow_type=workflow_type,
            status=WorkflowStatus.CREATED,
            current_step=first_step,
            state=state_cls(user_message=user_message),
            pending_action_token=None,
            slack_channel_id=slack_channel_id,
            slack_user_id=slack_user_id,
            slack_message_ts=None,
            created_at=now,
            ttl=now + WORKFLOW_TTL_SECONDS,
        )

    def to_item(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "workflow_type": self.workflow_type,
            "status": self.status.value,
            "current_step": self.current_step,
            "state": self.state.to_dict(),
            "pending_action_token": self.pending_action_token,
            "slack_channel_id": self.slack_channel_id,
            "slack_user_id": self.slack_user_id,
            "slack_message_ts": self.slack_message_ts,
            "created_at": self.created_at,
            "ttl": self.ttl,
        }

    @classmethod
    def from_item(cls, item: dict) -> WorkflowInstance:
        workflow_type = item["workflow_type"]
        state_cls = _STATE_CLS.get(workflow_type)
        if state_cls is None:
            raise KeyError(f"No state class registered for workflow_type={workflow_type}")
        return cls(
            workflow_id=item["workflow_id"],
            workflow_type=workflow_type,
            status=WorkflowStatus(item["status"]),
            current_step=item["current_step"],
            state=state_cls.from_dict(item["state"]),
            pending_action_token=item.get("pending_action_token"),
            slack_channel_id=item["slack_channel_id"],
            slack_user_id=item["slack_user_id"],
            slack_message_ts=item.get("slack_message_ts"),
            created_at=int(item["created_at"]),
            ttl=int(item["ttl"]),
        )


class IWorkflowInstanceRepository(ABC):
    """WorkflowInstance 저장소 인터페이스."""

    @abstractmethod
    async def save(self, instance: WorkflowInstance) -> None: ...

    @abstractmethod
    async def get(self, workflow_id: str) -> WorkflowInstance | None: ...
