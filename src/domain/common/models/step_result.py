"""Step 실행 결과 모델."""

from typing import Literal

from pydantic import BaseModel, Field


class StepResult(BaseModel):
    status: Literal["success", "waiting", "failed"]
    state_patch: dict = Field(default_factory=dict)
    control_signal: Literal["continue", "wait_for_user", "stop"] = "continue"
    next_step: str | None = None
    user_action_request: dict | None = None
    internal_trace: dict | None = None
