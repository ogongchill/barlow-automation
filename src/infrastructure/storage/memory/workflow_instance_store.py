"""WorkflowInstance 인메모리 저장소 -- 로컬 개발용."""

from src.domain.common.models.workflow_instance import IWorkflowInstanceRepository
from src.domain.common.models.workflow_instance import WorkflowInstance


class MemoryWorkflowInstanceStore(IWorkflowInstanceRepository):
    """딕셔너리 기반 인메모리 IWorkflowInstanceRepository."""

    def __init__(self) -> None:
        self._store: dict[str, WorkflowInstance] = {}

    async def save(self, instance: WorkflowInstance) -> None:
        self._store[instance.workflow_id] = instance

    async def get(self, workflow_id: str) -> WorkflowInstance | None:
        return self._store.get(workflow_id)
