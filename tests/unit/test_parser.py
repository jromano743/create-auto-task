from pathlib import Path

import pytest

from create_auto_task.core.exceptions import CATParseError, CATValidationError
from create_auto_task.core.parser import dump_task, load_task, parse_task

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_load_valid_task():
    task = load_task(FIXTURES / "valid_task.json")
    assert task.metadata.name == "Test task"
    assert task.actions[0].command == "WAIT"


def test_parse_invalid_json():
    with pytest.raises(CATParseError, match="Invalid JSON"):
        parse_task("{not json")


def test_invalid_document_raises_validation_error():
    with pytest.raises(CATValidationError):
        load_task(FIXTURES / "invalid_task.json")


def test_dump_and_parse_round_trip():
    task = load_task(FIXTURES / "valid_task.json")
    assert parse_task(dump_task(task)) == task
