from pathlib import Path

from create_auto_task.app.config import AppPaths
from create_auto_task.interfaces.cli import cli
from create_auto_task.storage.catalog_service import CatalogService
from create_auto_task.storage.json_repository import JSONTaskRepository
from create_auto_task.storage.sqlite_repository import SQLiteRepository

FIXTURE = Path(__file__).parents[1] / "fixtures" / "valid_task.json"


def make_service(tmp_path: Path) -> CatalogService:
    paths = AppPaths(
        root=tmp_path,
        tasks=tmp_path / "tasks",
        database=tmp_path / "database",
        logs=tmp_path / "logs",
        config=tmp_path / "config",
    )
    paths.ensure_directories()
    return CatalogService(
        JSONTaskRepository(paths.tasks),
        SQLiteRepository(paths.database / "catalog.sqlite3"),
    )


def test_validate_command_accepts_valid_task(capsys):
    assert cli.command_validate(FIXTURE) == 0
    assert "Valid CAT 1.0" in capsys.readouterr().out


def test_sync_and_list_commands(tmp_path, capsys):
    service = make_service(tmp_path)
    service.save_task(cli.load_task(FIXTURE))

    assert cli.command_sync(service) == 0
    assert "Indexed: 1" in capsys.readouterr().out
    assert cli.command_list(service) == 0
    assert "Test task" in capsys.readouterr().out


def test_history_command_shows_recorded_execution(tmp_path, capsys):
    service = make_service(tmp_path)
    task = cli.load_task(FIXTURE)
    service.record_execution(
        task_id=str(task.id), task_name=task.metadata.name,
        started_at="2026-10-03T12:00:00+00:00", finished_at="2026-10-03T12:00:01+00:00",
        status="COMPLETED", completed_actions=1, total_actions=1,
    )
    assert cli.command_history(service) == 0
    assert "COMPLETED" in capsys.readouterr().out


def test_run_records_successful_execution(tmp_path, monkeypatch, capsys):
    service = make_service(tmp_path)

    class FakeBackend:
        def __init__(self, **_kwargs):
            pass

        def wait(self, _seconds):
            pass

    monkeypatch.setattr(cli, "PyAutoGUIBackend", FakeBackend)
    assert cli.command_run(FIXTURE, service) == 0
    history = service.list_history()
    assert len(history) == 1
    assert history[0]["status"] == "COMPLETED"
    assert history[0]["completed_actions"] == 1
    assert "TASK_COMPLETED" in capsys.readouterr().out


def test_parser_exposes_subcommands():
    parser = cli.build_parser()
    for command in ("list", "validate", "run", "sync", "history"):
        assert command in parser.format_help()


def test_run_records_failed_execution(tmp_path, monkeypatch, capsys):
    service = make_service(tmp_path)

    class BrokenBackend:
        def __init__(self, **_kwargs):
            pass

        def wait(self, _seconds):
            raise RuntimeError("simulated backend failure")

    monkeypatch.setattr(cli, "PyAutoGUIBackend", BrokenBackend)
    assert cli.command_run(FIXTURE, service) == 1
    history = service.list_history()
    assert history[0]["status"] == "FAILED"
    assert history[0]["failed_actions"] == [1]
    assert "simulated backend failure" in history[0]["error"]
    assert "Execution failed" in capsys.readouterr().err
