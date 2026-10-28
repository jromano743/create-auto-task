"""Application paths and configuration defaults."""

from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Resolved writable paths used by the application."""

    root: Path
    tasks: Path
    database: Path
    logs: Path
    config: Path

    @classmethod
    def default(cls) -> "AppPaths":
        root = Path(user_data_path("CreateAutoTask", appauthor=False))
        return cls(
            root=root,
            tasks=root / "tasks",
            database=root / "database",
            logs=root / "logs",
            config=root / "config",
        )

    def ensure_directories(self) -> None:
        for path in (self.tasks, self.database, self.logs, self.config):
            path.mkdir(parents=True, exist_ok=True)
