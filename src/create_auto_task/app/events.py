"""Execution event definitions shared by CLI and GUI."""
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    TASK_STARTED = "TASK_STARTED"
    ACTION_STARTED = "ACTION_STARTED"
    ACTION_COMPLETED = "ACTION_COMPLETED"
    ACTION_FAILED = "ACTION_FAILED"
    TASK_PROGRESS = "TASK_PROGRESS"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_CANCELLED = "TASK_CANCELLED"


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    type: EventType
    task_id: str
    message: str = ""
    action_id: int | None = None
    current: int = 0
    total: int = 0
    details: dict[str, Any] = field(default_factory=dict)
