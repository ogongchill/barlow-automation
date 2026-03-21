"""Step 실행 인터페이스."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Step(Protocol):
    async def execute(self, input: Any) -> Any: ...
