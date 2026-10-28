import json
from pathlib import Path

from create_auto_task.core.parser import load_task
from create_auto_task.storage.catalog_service import CatalogService
from create_auto_task.storage.json_repository import JSONTaskRepository
from create_auto_task.storage.sqlite_repository import SQLiteRepository

FIXTURE = Path(__file__).parents[1] / "fixtures" / "valid_task.json"


def build_service(tmp_path):
    json_repo = JSONTaskRepository(tmp_path / "tasks")
    sqlite_repo = SQLiteRepository(tmp_path / "db" / "catalog.sqlite3")
    return CatalogService(json_repo, sqlite_repo), json_repo, sqlite_repo


def test_save_indexes_and_external_edit_updates_hash(tmp_path):
    service, json_repo, sqlite_repo = build_service(tmp_path)
    task = load_task(FIXTURE)
    path = service.save_task(task)
    before = sqlite_repo.get_task(str(task.id))["sha256"]

    data = json.loads(path.read_text(encoding="utf-8"))
    data["metadata"]["name"] = "Edited externally"
    path.write_text(json.dumps(data), encoding="utf-8")

    loaded = service.get_task(str(task.id))
    after = sqlite_repo.get_task(str(task.id))["sha256"]
    assert loaded.metadata.name == "Edited externally"
    assert before != after
    assert service.list_tasks()[0]["name"] == "Edited externally"


def test_refresh_rebuilds_catalog_from_json_files(tmp_path):
    service, json_repo, sqlite_repo = build_service(tmp_path)
    task = load_task(FIXTURE)
    json_repo.save(task)

    result = service.refresh()
    assert result.indexed == 1
    assert result.errors == ()
    assert len(sqlite_repo.list_tasks()) == 1


def test_refresh_skips_invalid_json_and_reports_it(tmp_path):
    service, json_repo, sqlite_repo = build_service(tmp_path)
    (json_repo.root / "broken.json").write_text("{not json", encoding="utf-8")
    result = service.refresh()
    assert result.indexed == 0
    assert len(result.errors) == 1
    assert sqlite_repo.list_tasks() == []


def test_delete_removes_catalog_entry_but_history_is_retained(tmp_path):
    service, _json_repo, sqlite_repo = build_service(tmp_path)
    task = load_task(FIXTURE)
    service.save_task(task)
    service.record_execution(
        task_id=str(task.id), task_name=task.metadata.name,
        started_at="2026-10-02T00:00:00+00:00", finished_at=None,
        status="CANCELLED", completed_actions=0, total_actions=1,
    )
    assert service.delete_task(str(task.id)) is True
    assert service.list_tasks() == []
    assert len(service.list_history(task_id=str(task.id))) == 1
