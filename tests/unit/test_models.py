from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from create_auto_task.core.models import Action, CATTask, TaskMetadata, TaskSettings


def test_action_rejects_invalid_command_name():
    with pytest.raises(ValidationError):
        Action(id=1, command="click mouse", params={})


def test_metadata_requires_timezone():
    with pytest.raises(ValidationError):
        TaskMetadata(name="Task", created_at=datetime(2026, 10, 1))


def test_retry_policy_requires_retry_count():
    with pytest.raises(ValidationError):
        TaskSettings(error_policy="RETRY")


def test_duplicate_action_ids_are_rejected():
    with pytest.raises(ValidationError):
        CATTask(
            format="CAT", version="1.0", id="c4c40b2d-1234-4567-8901-123456789abc",
            metadata={"name": "Task", "created_at": datetime.now(timezone.utc)},
            actions=[{"id": 1, "command": "WAIT"}, {"id": 1, "command": "WAIT"}],
        )
