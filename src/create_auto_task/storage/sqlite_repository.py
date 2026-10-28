"""SQLite repository for task metadata and execution history (never task bodies)."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from create_auto_task.storage.migrations import migrate


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            migrate(connection)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def upsert_task(
        self, *, task_id: str, name: str, description: str, created_at: str,
        file_path: str, sha256: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO tasks
                   (task_id, name, description, created_at, file_path, sha256, indexed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(task_id) DO UPDATE SET
                     name=excluded.name, description=excluded.description,
                     created_at=excluded.created_at, file_path=excluded.file_path,
                     sha256=excluded.sha256, indexed_at=excluded.indexed_at""",
                (task_id, name, description, created_at, file_path, sha256, utc_now()),
            )

    def remove_missing_tasks(self, existing_paths: set[str]) -> int:
        with self._connect() as connection:
            rows = connection.execute("SELECT task_id, file_path FROM tasks").fetchall()
            missing = [row["task_id"] for row in rows if row["file_path"] not in existing_paths]
            connection.executemany("DELETE FROM tasks WHERE task_id = ?", [(item,) for item in missing])
            return len(missing)

    def list_tasks(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT task_id, name, description, created_at, file_path, sha256, indexed_at "
                "FROM tasks ORDER BY name COLLATE NOCASE, task_id"
            ).fetchall()
            return [dict(row) for row in rows]

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            return dict(row) if row else None

    def record_execution(
        self, *, task_id: str, task_name: str, started_at: str,
        finished_at: str | None, status: str, completed_actions: int,
        total_actions: int, failed_actions: list[int] | tuple[int, ...] = (),
        error: str | None = None,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO execution_history
                   (task_id, task_name, started_at, finished_at, status,
                    completed_actions, total_actions, failed_actions, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (task_id, task_name, started_at, finished_at, status, completed_actions,
                 total_actions, json.dumps(list(failed_actions)), error),
            )
            return int(cursor.lastrowid)

    def list_history(self, *, task_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        query = "SELECT * FROM execution_history"
        params: tuple[Any, ...] = ()
        if task_id is not None:
            query += " WHERE task_id = ?"
            params = (task_id,)
        query += " ORDER BY started_at DESC, id DESC LIMIT ?"
        params += (limit,)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
            result = [dict(row) for row in rows]
        for item in result:
            item["failed_actions"] = json.loads(item["failed_actions"])
        return result
