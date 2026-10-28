"""Functional command-line interface for Create Auto Task."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from create_auto_task import __version__
from create_auto_task.app.config import AppPaths
from create_auto_task.app.events import EventType, ExecutionEvent
from create_auto_task.backends.execution import PyAutoGUIBackend
from create_auto_task.core.engine import ExecutionEngine
from create_auto_task.core.exceptions import CATError
from create_auto_task.core.parser import dump_task, load_task
from create_auto_task.recorder.listener import PynputRecorder
from create_auto_task.recorder.session import RecorderSession
from create_auto_task.core.validator import validate_task
from create_auto_task.storage.catalog_service import CatalogService
from create_auto_task.storage.json_repository import JSONTaskRepository
from create_auto_task.storage.sqlite_repository import SQLiteRepository


def build_service(paths: AppPaths | None = None) -> CatalogService:
    """Create the shared JSON/SQLite persistence services."""
    paths = paths or AppPaths.default()
    paths.ensure_directories()
    return CatalogService(
        JSONTaskRepository(paths.tasks),
        SQLiteRepository(paths.database / "catalog.sqlite3"),
    )


def command_list(service: CatalogService) -> int:
    sync = service.refresh()
    for error in sync.errors:
        print(f"WARN: {error}", file=sys.stderr)
    tasks = service.list_tasks()
    if not tasks:
        print("No tasks found.")
        return 0
    print(f"{'ID':36}  {'NAME':30}  ACTIONS")
    for item in tasks:
        # Action count is intentionally not duplicated in SQLite; load source JSON.
        task = load_task(item["file_path"])
        print(f"{item['task_id']:36}  {item['name'][:30]:30}  {len(task.actions)}")
    return 0


def command_validate(path: str | Path) -> int:
    task = load_task(path)
    validate_task(task)
    print(f"Valid CAT {task.version}: {task.metadata.name}")
    print(f"ID: {task.id} | Actions: {len(task.actions)}")
    return 0


def command_sync(service: CatalogService) -> int:
    result = service.refresh()
    print(f"Indexed: {result.indexed} | Removed: {result.removed} | Errors: {len(result.errors)}")
    for error in result.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if result.errors else 0


def command_history(service: CatalogService, *, task_id: str | None = None, limit: int = 20) -> int:
    entries = service.list_history(task_id=task_id, limit=limit)
    if not entries:
        print("No execution history found.")
        return 0
    for item in entries:
        finished = item["finished_at"] or "(in progress)"
        print(
            f"#{item['id']} {item['started_at']} | {item['status']:<9} | "
            f"{item['task_name']} | {item['completed_actions']}/{item['total_actions']} "
            f"| finished: {finished}"
        )
        if item["error"]:
            print(f"  Error: {item['error']}")
    return 0


def command_run(path: str | Path, service: CatalogService) -> int:
    task = load_task(path)
    validate_task(task)
    service.save_task(task)
    started_at = datetime.now(timezone.utc).isoformat()
    completed = 0
    failed: list[int] = []
    status = "FAILED"
    error: str | None = None
    try:
        backend = PyAutoGUIBackend(
            fail_safe=task.settings.fail_safe,
            speed=task.settings.speed,
        )

        def collect(event: ExecutionEvent) -> None:
            nonlocal completed
            if event.type == EventType.ACTION_COMPLETED:
                completed += 1
            elif event.type == EventType.ACTION_FAILED and event.action_id is not None:
                failed.append(event.action_id)
            print(f"[{event.type}] {event.message}")

        result = ExecutionEngine(backend).run(task, on_event=collect)
        status = "CANCELLED" if result.cancelled else ("FAILED" if result.failed_actions else "COMPLETED")
        completed = result.completed_actions
        failed = list(result.failed_actions)
        print(f"Result: {status} ({completed}/{result.total_actions} actions)")
    except Exception as exc:  # preserve a failed execution in history before returning
        error = f"{type(exc).__name__}: {exc}"
        print(f"Execution failed: {error}", file=sys.stderr)
    finally:
        service.record_execution(
            task_id=str(task.id),
            task_name=task.metadata.name,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
            status=status,
            completed_actions=completed,
            total_actions=len(task.actions),
            failed_actions=failed,
            error=error,
        )
    return 1 if status == "FAILED" else 0


def command_record(name: str, output: str | Path, *, description: str = "") -> int:
    """Record desktop input until Escape is held for three seconds."""
    destination = Path(output).expanduser()
    session = RecorderSession(name, description)
    recorder = PynputRecorder(session)
    recorder.start()
    print("Recording started. Hold Escape for 3 seconds to stop and save.")
    try:
        recorder.wait()
    except KeyboardInterrupt:
        recorder.stop()
        print("Recording cancelled with Ctrl+C; task was not saved.")
        return 130
    task = recorder.stop()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(dump_task(task) + "\n", encoding="utf-8")
    print(f"Saved: {destination} ({len(task.actions)} actions)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="create-auto-task",
        description="Record and execute desktop automation tasks.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List tasks in the local catalog")
    validate_parser = subparsers.add_parser("validate", help="Validate a CAT JSON file")
    validate_parser.add_argument("path", type=Path)
    run_parser = subparsers.add_parser("run", help="Execute a CAT JSON file")
    run_parser.add_argument("path", type=Path)
    record_parser = subparsers.add_parser("record", help="Record keyboard and mouse actions")
    record_parser.add_argument("name", help="Name for the recorded task")
    record_parser.add_argument("output", type=Path, help="Destination CAT JSON file")
    record_parser.add_argument("--description", default="")
    subparsers.add_parser("sync", help="Rebuild the local task catalog")
    history_parser = subparsers.add_parser("history", help="Show recent executions")
    history_parser.add_argument("--task-id")
    history_parser.add_argument("--limit", type=int, default=20)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return command_validate(args.path)
        if args.command == "record":
            return command_record(args.name, args.output, description=args.description)
        service = build_service()
        if args.command == "list":
            return command_list(service)
        if args.command == "sync":
            return command_sync(service)
        if args.command == "history":
            if args.limit < 1:
                parser.error("--limit must be >= 1")
            return command_history(service, task_id=args.task_id, limit=args.limit)
        if args.command == "run":
            return command_run(args.path, service)
    except (CATError, OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0
