from pathlib import Path

import pytest

from create_auto_task.core.exceptions import CATValidationError
from create_auto_task.core.parser import load_task
from create_auto_task.core.validator import validate_task

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_valid_task_passes_semantic_validation():
    task = load_task(FIXTURES / "valid_task.json")
    assert validate_task(task) is task


def test_unknown_command_is_rejected():
    task = load_task(FIXTURES / "valid_task.json")
    task.actions[0].command = "RUN_SHELL"
    with pytest.raises(CATValidationError, match="unsupported command"):
        validate_task(task)


def test_missing_parameter_is_rejected():
    task = load_task(FIXTURES / "valid_task.json")
    task.actions[0].params = {}
    with pytest.raises(CATValidationError, match="missing required params"):
        validate_task(task)


def test_wrong_parameter_type_is_rejected():
    task = load_task(FIXTURES / "valid_task.json")
    task.actions[0].params = {"seconds": "soon"}
    with pytest.raises(CATValidationError, match="must be a number"):
        validate_task(task)
