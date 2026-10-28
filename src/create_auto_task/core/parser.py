"""Decode CAT JSON documents into validated models."""

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .exceptions import CATParseError, CATValidationError
from .models import CATTask


def parse_task(data: str | bytes | dict[str, Any]) -> CATTask:
    """Parse JSON text, bytes, or a decoded mapping into a CAT task."""
    try:
        if isinstance(data, (str, bytes)):
            payload = json.loads(data)
        elif isinstance(data, dict):
            payload = data
        else:
            raise CATParseError("CAT input must be JSON text, bytes, or a dictionary")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CATParseError(f"Invalid JSON: {exc}") from exc

    try:
        return CATTask.model_validate(payload)
    except ValidationError as exc:
        raise CATValidationError(str(exc)) from exc


def load_task(path: str | Path) -> CATTask:
    """Load and parse a CAT task from a UTF-8 JSON file."""
    file_path = Path(path)
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CATParseError(f"Could not read task file '{file_path}': {exc}") from exc
    return parse_task(content)


def dump_task(task: CATTask, *, indent: int = 2) -> str:
    """Serialize a task to stable, human-editable JSON."""
    return json.dumps(task.model_dump(mode="json"), ensure_ascii=False, indent=indent)
