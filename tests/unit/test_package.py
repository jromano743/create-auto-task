from create_auto_task import __version__
from create_auto_task.app.config import AppPaths


def test_package_version_is_defined():
    assert __version__ == "0.8.2"


def test_default_paths_are_distinct():
    paths = AppPaths.default()
    assert paths.tasks != paths.database
    assert paths.logs != paths.config


def test_visual_editor_helpers_renumber_and_clone():
    from create_auto_task.core.models import Action, CATTask, TaskMetadata
    from create_auto_task.interfaces.gui.main_window import clone_task, renumber_actions
    from datetime import datetime, timezone
    from uuid import uuid4

    task = CATTask(
        format="CAT", version="1.0", id=uuid4(),
        metadata=TaskMetadata(name="Demo", created_at=datetime.now(timezone.utc)),
        actions=[Action(id=8, command="WAIT", params={"seconds": 1.0}), Action(id=42, command="TYPE", params={"text": "ok"})],
    )
    copied = clone_task(task, name="Copia", new_id=True)
    assert [a.id for a in copied.actions] == [1, 2]
    assert copied.metadata.name == "Copia"
    assert copied.id != task.id
    assert copied.actions[1].params is not task.actions[1].params


def test_gui_has_a_connected_stop_recording_control():
    from pathlib import Path
    source = (Path(__file__).parents[2] / "src/create_auto_task/interfaces/gui/main_window.py").read_text()
    assert 'QPushButton("■ Detener grabación")' in source
    assert "self.stop_record_btn.clicked.connect(self.stop_recording)" in source
    assert "self.stop_record_btn.setEnabled(recording)" in source
