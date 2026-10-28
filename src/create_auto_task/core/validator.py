"""Semantic validation for commands in CAT tasks."""

from typing import Any

from .exceptions import CATValidationError
from .models import CATTask

# Command schemas are intentionally allow-listed. JSON cannot invoke arbitrary code.
COMMAND_REQUIRED_PARAMS: dict[str, set[str]] = {
    "CLICK": {"x", "y"},
    "DOUBLE_CLICK": {"x", "y"},
    "MOVE": {"x", "y"},
    "SCROLL": {"amount"},
    "KEY": {"key"},
    "HOTKEY": {"keys"},
    "TYPE": {"text"},
    "WAIT": {"seconds"},
}


def _validate_param_types(command: str, params: dict[str, Any], action_id: int) -> list[str]:
    errors: list[str] = []
    numeric = {"x", "y", "amount", "seconds"}
    for key in numeric & params.keys():
        value = params[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"action {action_id}: '{key}' must be a number")
    if command == "WAIT" and isinstance(params.get("seconds"), (int, float)):
        if isinstance(params["seconds"], bool) or params["seconds"] < 0:
            errors.append(f"action {action_id}: 'seconds' must be >= 0")
    if command in {"CLICK", "DOUBLE_CLICK", "MOVE"}:
        for key in ("x", "y"):
            if key in params and isinstance(params[key], (int, float)) and not isinstance(params[key], bool):
                if params[key] < 0:
                    errors.append(f"action {action_id}: '{key}' must be >= 0")
    if command in {"KEY", "TYPE"} and command == "KEY":
        if not isinstance(params.get("key"), str) or not params["key"].strip():
            errors.append(f"action {action_id}: 'key' must be a non-empty string")
    if command == "TYPE" and not isinstance(params.get("text"), str):
        errors.append(f"action {action_id}: 'text' must be a string")
    if command == "HOTKEY":
        keys = params.get("keys")
        if not isinstance(keys, list) or len(keys) < 2 or not all(isinstance(k, str) and k for k in keys):
            errors.append(f"action {action_id}: 'keys' must be a list of at least two non-empty strings")
    return errors


def validate_task(task: CATTask) -> CATTask:
    """Check that every action uses a supported command and valid parameters."""
    errors: list[str] = []
    for action in task.actions:
        required = COMMAND_REQUIRED_PARAMS.get(action.command)
        if required is None:
            errors.append(f"action {action.id}: unsupported command '{action.command}'")
            continue
        missing = required - action.params.keys()
        unexpected = action.params.keys() - required
        if missing:
            errors.append(f"action {action.id}: missing required params: {', '.join(sorted(missing))}")
        if unexpected:
            errors.append(f"action {action.id}: unexpected params: {', '.join(sorted(unexpected))}")
        if missing or unexpected:
            continue
        errors.extend(_validate_param_types(action.command, action.params, action.id))
    if errors:
        raise CATValidationError("\n".join(errors))
    return task
