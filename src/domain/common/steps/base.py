"""Step 실행 인터페이스."""

from typing import Protocol, runtime_checkable, Any

from src.domain.common.models.step_result import StepResult


@runtime_checkable
class Step(Protocol):
    async def execute(self, state: Any) -> StepResult: ...
