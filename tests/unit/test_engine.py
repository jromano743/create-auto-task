from pathlib import Path
from threading import Event

import pytest

from create_auto_task.app.events import EventType
from create_auto_task.core.engine import ExecutionEngine
from create_auto_task.core.exceptions import CATExecutionError
from create_auto_task.core.models import ErrorPolicy, TaskSettings
from create_auto_task.core.parser import load_task

FIXTURES = Path(__file__).parents[1] / "fixtures"


class FakeBackend:
    def __init__(self, *, fail_first_wait: bool = False) -> None:
        self.calls: list[tuple] = []
        self.fail_first_wait = fail_first_wait

    def click(self, x, y): self.calls.append(("click", x, y))
    def double_click(self, x, y): self.calls.append(("double_click", x, y))
    def move(self, x, y): self.calls.append(("move", x, y))
    def scroll(self, amount): self.calls.append(("scroll", amount))
    def press(self, key): self.calls.append(("press", key))
    def hotkey(self, keys): self.calls.append(("hotkey", keys))
    def write(self, text): self.calls.append(("write", text))
    def wait(self, seconds):
        self.calls.append(("wait", seconds))
        if self.fail_first_wait and len([call for call in self.calls if call[0] == "wait"]) == 1:
            raise RuntimeError("temporary failure")



def test_engine_executes_sequentially_and_emits_events():
    task = load_task(FIXTURES / "valid_task.json")
    backend = FakeBackend()
    events = []
    result = ExecutionEngine(backend).run(task, on_event=events.append)
    assert backend.calls == [("wait", 0.5)]
    assert result.completed_actions == result.total_actions == 1
    assert [event.type for event in events] == [
        EventType.TASK_STARTED, EventType.ACTION_STARTED, EventType.ACTION_COMPLETED,
        EventType.TASK_PROGRESS, EventType.TASK_COMPLETED,
    ]


def test_stop_policy_raises_on_backend_failure():
    task = load_task(FIXTURES / "valid_task.json")
    backend = FakeBackend(fail_first_wait=True)
    with pytest.raises(CATExecutionError, match="Action 1"):
        ExecutionEngine(backend).run(task)


def test_continue_policy_records_failure_and_runs_next_action():
    task = load_task(FIXTURES / "valid_task.json")
    task.settings.error_policy = ErrorPolicy.CONTINUE
    task.actions.append(task.actions[0].model_copy(update={"id": 2}))
    backend = FakeBackend(fail_first_wait=True)
    result = ExecutionEngine(backend).run(task)
    assert result.failed_actions == (1,)
    assert result.completed_actions == 1
    assert result.total_actions == 2


def test_retry_policy_retries_configured_number_of_times():
    task = load_task(FIXTURES / "valid_task.json")
    task.settings = TaskSettings(error_policy=ErrorPolicy.RETRY, retry_count=1)
    backend = FakeBackend(fail_first_wait=True)
    result = ExecutionEngine(backend).run(task)
    assert result.completed_actions == 1
    assert backend.calls == [("wait", 0.5), ("wait", 0.5)]


def test_cancelled_task_stops_before_first_action():
    task = load_task(FIXTURES / "valid_task.json")
    cancel = Event()
    cancel.set()
    events = []
    result = ExecutionEngine(FakeBackend()).run(task, on_event=events.append, cancel_event=cancel)
    assert result.cancelled is True
    assert result.completed_actions == 0
    assert events[-1].type == EventType.TASK_CANCELLED


def test_cancellation_is_checked_between_actions():
    task = load_task(FIXTURES / "valid_task.json")
    task.actions.append(task.actions[0].model_copy(update={"id": 2}))
    cancel = Event()
    events = []

    def stop_after_first_action(event):
        events.append(event)
        if event.type == EventType.ACTION_COMPLETED:
            cancel.set()

    result = ExecutionEngine(FakeBackend()).run(
        task, on_event=stop_after_first_action, cancel_event=cancel
    )
    assert result.cancelled is True
    assert result.completed_actions == 1
    assert events[-1].type == EventType.TASK_CANCELLED
