"""Workflow 및 Step 상태 열거형."""

from enum import Enum


class WorkflowStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class StepStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
