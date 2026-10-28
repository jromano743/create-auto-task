from create_auto_task.storage.sqlite_repository import SQLiteRepository


def test_catalog_upsert_and_history(tmp_path):
    repository = SQLiteRepository(tmp_path / "catalog.sqlite3")
    repository.upsert_task(
        task_id="task-1", name="Demo", description="", created_at="2026-10-01T00:00:00+00:00",
        file_path="/tasks/task-1.json", sha256="a" * 64,
    )
    repository.upsert_task(
        task_id="task-1", name="Renamed", description="updated", created_at="2026-10-01T00:00:00+00:00",
        file_path="/tasks/task-1.json", sha256="b" * 64,
    )
    tasks = repository.list_tasks()
    assert len(tasks) == 1
    assert tasks[0]["name"] == "Renamed"
    assert tasks[0]["sha256"] == "b" * 64

    entry_id = repository.record_execution(
        task_id="task-1", task_name="Renamed", started_at="2026-10-02T00:00:00+00:00",
        finished_at="2026-10-02T00:00:01+00:00", status="COMPLETED",
        completed_actions=2, total_actions=2, failed_actions=[3],
    )
    history = repository.list_history(task_id="task-1")
    assert history[0]["id"] == entry_id
    assert history[0]["failed_actions"] == [3]


def test_database_schema_is_migrated_once(tmp_path):
    path = tmp_path / "catalog.sqlite3"
    SQLiteRepository(path)
    SQLiteRepository(path)
    repository = SQLiteRepository(path)
    assert repository.list_tasks() == []
