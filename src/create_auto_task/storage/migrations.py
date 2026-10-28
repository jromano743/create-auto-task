"""SQLite schema migrations for the local catalog and execution history."""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
    )
    row = connection.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    current = int(row[0]) if row else 0

    if current < 1:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                sha256 TEXT NOT NULL,
                indexed_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_name ON tasks(name COLLATE NOCASE);
            CREATE TABLE IF NOT EXISTS execution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                task_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                completed_actions INTEGER NOT NULL DEFAULT 0,
                total_actions INTEGER NOT NULL DEFAULT 0,
                failed_actions TEXT NOT NULL DEFAULT '[]',
                error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_history_task_started
                ON execution_history(task_id, started_at DESC);
            """
        )
        connection.execute("DELETE FROM schema_version")
        connection.execute("INSERT INTO schema_version(version) VALUES (1)")

    if current > SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema version {current} is newer than supported {SCHEMA_VERSION}"
        )
