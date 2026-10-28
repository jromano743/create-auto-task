"""Coordinates the JSON source of truth with the rebuildable SQLite catalog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from create_auto_task.core.models import CATTask
from create_auto_task.storage.json_repository import JSONTaskRepository
from create_auto_task.storage.sqlite_repository import SQLiteRepository


@dataclass(frozen=True, slots=True)
class CatalogSyncResult:
    indexed: int
    removed: int
    errors: tuple[str, ...] = ()


class CatalogService:
    def __init__(self, json_repository: JSONTaskRepository, sqlite_repository: SQLiteRepository) -> None:
        self.json = json_repository
        self.sqlite = sqlite_repository

    def save_task(self, task: CATTask) -> Path:
        path = self.json.save(task)
        self._index(task, path)
        return path

    def get_task(self, task_id: str) -> CATTask:
        task = self.json.load(task_id)
        path = self.json.path_for(task_id)
        # Refresh the index if the JSON was edited outside the application.
        self._index(task, path)
        return task

    def delete_task(self, task_id: str) -> bool:
        deleted = self.json.delete(task_id)
        if deleted:
            self.sqlite.remove_missing_tasks({str(path.resolve()) for path in self.json.list_paths()})
        return deleted

    def list_tasks(self) -> list[dict[str, Any]]:
        return self.sqlite.list_tasks()

    def refresh(self) -> CatalogSyncResult:
        indexed = 0
        errors: list[str] = []
        paths = self.json.list_paths()
        for path in paths:
            try:
                task = self.json.load_path(path)
                self._index(task, path)
                indexed += 1
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
        removed = self.sqlite.remove_missing_tasks({str(path.resolve()) for path in paths})
        return CatalogSyncResult(indexed=indexed, removed=removed, errors=tuple(errors))

    def record_execution(self, **record: Any) -> int:
        return self.sqlite.record_execution(**record)

    def list_history(self, *, task_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return self.sqlite.list_history(task_id=task_id, limit=limit)

    def _index(self, task: CATTask, path: Path) -> None:
        self.sqlite.upsert_task(
            task_id=str(task.id), name=task.metadata.name,
            description=task.metadata.description,
            created_at=task.metadata.created_at.isoformat(),
            file_path=str(path.resolve()), sha256=self.json.sha256(path),
        )
