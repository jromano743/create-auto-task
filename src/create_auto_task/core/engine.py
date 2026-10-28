"""Sequential CAT task execution engine, independent from CLI and GUI."""
from dataclasses import dataclass
from threading import Event
from typing import Callable

from create_auto_task.app.events import EventType, ExecutionEvent
from create_auto_task.backends.execution import ExecutionBackend
from create_auto_task.core.exceptions import CATCancelled, CATExecutionError
from create_auto_task.core.interpreter import Interpreter
from create_auto_task.core.models import CATTask, ErrorPolicy
from create_auto_task.core.registry import CommandRegistry
from create_auto_task.core.validator import validate_task

EventCallback = Callable[[ExecutionEvent], None]


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    task_id: str
    completed_actions: int
    total_actions: int
    failed_actions: tuple[int, ...] = ()
    cancelled: bool = False


class ExecutionEngine:
    def __init__(self, backend: ExecutionBackend, registry: CommandRegistry | None = None) -> None:
        self.backend = backend
        self.registry = registry or CommandRegistry.default()

    def run(
        self,
        task: CATTask,
        *,
        on_event: EventCallback | None = None,
        cancel_event: Event | None = None,
    ) -> ExecutionResult:
        validate_task(task)
        cancel_event = cancel_event or Event()
        emit = on_event or (lambda _event: None)
        task_id = str(task.id)
        total = len(task.actions)
        completed = 0
        failed: list[int] = []
        interpreter = Interpreter(self.registry, self.backend)
        emit(ExecutionEvent(EventType.TASK_STARTED, task_id, "Task started", total=total))

        for index, action in enumerate(task.actions, start=1):
            if cancel_event.is_set():
                emit(ExecutionEvent(EventType.TASK_CANCELLED, task_id, "Task cancelled", action.id, completed, total))
                return ExecutionResult(task_id, completed, total, tuple(failed), True)

            emit(ExecutionEvent(EventType.ACTION_STARTED, task_id, action.command, action.id, index, total))
            attempts = task.settings.retry_count if task.settings.error_policy == ErrorPolicy.RETRY else 0
            for attempt in range(attempts + 1):
                try:
                    interpreter.execute(action)
                    completed += 1
                    emit(ExecutionEvent(EventType.ACTION_COMPLETED, task_id, "Action completed", action.id, index, total))
                    break
                except Exception as exc:  # backend errors are surfaced as execution events
                    final_attempt = attempt == attempts
                    if not final_attempt:
                        continue
                    failed.append(action.id)
                    emit(ExecutionEvent(
                        EventType.ACTION_FAILED, task_id, str(exc), action.id, index, total,
                        {"exception": type(exc).__name__, "attempts": attempt + 1},
                    ))
                    if task.settings.error_policy == ErrorPolicy.STOP:
                        raise CATExecutionError(f"Action {action.id} ({action.command}) failed: {exc}") from exc

            emit(ExecutionEvent(EventType.TASK_PROGRESS, task_id, "Task progress", action.id, index, total))

        result = ExecutionResult(task_id, completed, total, tuple(failed))
        emit(ExecutionEvent(EventType.TASK_COMPLETED, task_id, "Task completed", current=completed, total=total,
                            details={"failed_actions": failed}))
        return result
