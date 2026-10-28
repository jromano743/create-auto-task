from pathlib import Path

import pytest

from create_auto_task.core.parser import load_task
from create_auto_task.storage.json_repository import JSONTaskRepository

FIXTURE = Path(__file__).parents[1] / "fixtures" / "valid_task.json"


def test_save_and_load_round_trip(tmp_path):
    repository = JSONTaskRepository(tmp_path / "tasks")
    task = load_task(FIXTURE)
    path = repository.save(task)
    assert path.exists()
    assert path.name == f"{task.id}.json"
    assert repository.load(task.id) == task
    assert len(repository.sha256(path)) == 64


def test_delete_is_idempotent(tmp_path):
    repository = JSONTaskRepository(tmp_path)
    task = load_task(FIXTURE)
    repository.save(task)
    assert repository.delete(task.id) is True
    assert repository.delete(task.id) is False


def test_task_id_cannot_escape_repository(tmp_path):
    repository = JSONTaskRepository(tmp_path)
    with pytest.raises(ValueError):
        repository.path_for("../../outside")
