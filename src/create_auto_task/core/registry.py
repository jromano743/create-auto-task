"""Allow-listed mapping between CAT commands and backend operations."""
from collections.abc import Callable
from typing import Any

from create_auto_task.backends.execution import ExecutionBackend
from create_auto_task.core.exceptions import CATExecutionError
from create_auto_task.core.models import Action

Handler = Callable[[ExecutionBackend, dict[str, Any]], None]


def _call(method: str, *fields: str) -> Handler:
    def handler(backend: ExecutionBackend, params: dict[str, Any]) -> None:
        getattr(backend, method)(*(params[field] for field in fields))
    return handler


class CommandRegistry:
    """Registry containing only explicitly registered command handlers."""
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, command: str, handler: Handler) -> None:
        normalized = command.upper()
        if normalized in self._handlers:
            raise ValueError(f"Command already registered: {normalized}")
        self._handlers[normalized] = handler

    def execute(self, action: Action, backend: ExecutionBackend) -> None:
        handler = self._handlers.get(action.command)
        if handler is None:
            raise CATExecutionError(f"No handler registered for command '{action.command}'")
        handler(backend, action.params)

    @classmethod
    def default(cls) -> "CommandRegistry":
        registry = cls()
        registry.register("CLICK", _call("click", "x", "y"))
        registry.register("DOUBLE_CLICK", _call("double_click", "x", "y"))
        registry.register("MOVE", _call("move", "x", "y"))
        registry.register("SCROLL", _call("scroll", "amount"))
        registry.register("KEY", _call("press", "key"))
        registry.register("HOTKEY", _call("hotkey", "keys"))
        registry.register("TYPE", _call("write", "text"))
        registry.register("WAIT", _call("wait", "seconds"))
        return registry
