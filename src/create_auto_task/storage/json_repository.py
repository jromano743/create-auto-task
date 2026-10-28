"""Filesystem repository: CAT JSON documents remain the source of truth."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from uuid import UUID

from create_auto_task.core.models import CATTask
from create_auto_task.core.parser import dump_task, load_task


class JSONTaskRepository:
    """Store one portable CAT document per task using atomic replacement."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, task_id: UUID | str) -> Path:
        # UUID parsing prevents path traversal through externally supplied IDs.
        safe_id = UUID(str(task_id))
        return self.root / f"{safe_id}.json"

    def save(self, task: CATTask) -> Path:
        destination = self.path_for(task.id)
        payload = dump_task(task) + "\n"
        temp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", newline="\n", dir=self.root,
                prefix=f".{task.id}.", suffix=".tmp", delete=False,
            ) as handle:
                temp_name = handle.name
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, destination)
            temp_name = None
            # Persist the directory entry where the platform supports directory fsync.
            if hasattr(os, "O_DIRECTORY"):
                dir_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
        finally:
            if temp_name is not None:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass
        return destination

    def load(self, task_id: UUID | str) -> CATTask:
        return load_task(self.path_for(task_id))

    def load_path(self, path: str | Path) -> CATTask:
        """Load a CAT document by path (useful for imports and catalog scans)."""
        return load_task(path)

    def delete(self, task_id: UUID | str) -> bool:
        path = self.path_for(task_id)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False

    def list_paths(self) -> list[Path]:
        return sorted(path for path in self.root.glob("*.json") if path.is_file())

    @staticmethod
    def sha256(path: str | Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
