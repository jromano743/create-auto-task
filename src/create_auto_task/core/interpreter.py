"""Small interpreter that dispatches validated actions to the registry."""
from create_auto_task.backends.execution import ExecutionBackend
from create_auto_task.core.models import Action
from create_auto_task.core.registry import CommandRegistry


class Interpreter:
    def __init__(self, registry: CommandRegistry, backend: ExecutionBackend) -> None:
        self.registry = registry
        self.backend = backend

    def execute(self, action: Action) -> None:
        self.registry.execute(action, self.backend)
