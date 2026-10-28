# Create Auto Task

Create Auto Task is a cross-platform desktop automation application with a shared
execution core and CLI/GUI interfaces.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
python -m pip install --upgrade pip
python -m pip install -e ".[all,dev]"
```

## Run

```bash
python -m create_auto_task --help
```

The application is being refactored. The legacy implementation is preserved under
`legacy/original/` for reference and migration; it is not part of the active runtime.

## CAT 1.0 task format

Tasks are UTF-8 JSON documents using the versioned `CAT` format. The document
contains a stable UUID, metadata, execution settings, and an ordered list of
explicit actions. The parser validates the document structure; the semantic
validator checks the command allow-list and each command's parameters. Unknown
commands and parameters are rejected. CAT files never contain executable
Python or shell snippets.

The current command set is `CLICK`, `DOUBLE_CLICK`, `MOVE`, `SCROLL`, `KEY`,
`HOTKEY`, `TYPE`, and `WAIT`. See `examples/tasks/example.json` for a complete
example. `STOP` is the default error policy; `RETRY` requires an explicit
`retry_count`.


## Execution core (0.3.0)

The sequential `ExecutionEngine` consumes a validated `CATTask` and dispatches
actions through an allow-listed `CommandRegistry` to an `ExecutionBackend`.
The initial optional backend is PyAutoGUI; tests use a fake backend and never
control the real desktop. The engine emits typed events for task/action start,
completion, failure, progress, and cancellation. Cancellation is checked between
actions. Error policies are `STOP`, `CONTINUE`, and `RETRY` (with `retry_count`).

The core can be called independently of either interface:

```python
from create_auto_task.core.engine import ExecutionEngine
from create_auto_task.core.parser import load_task
from create_auto_task.backends.execution import PyAutoGUIBackend

task = load_task("examples/tasks/example.json")
backend = PyAutoGUIBackend(fail_safe=task.settings.fail_safe, speed=task.settings.speed)
result = ExecutionEngine(backend).run(task, on_event=print)
print(result)
```


## Persistence layer (0.4.0)

CAT task documents are stored as individual UTF-8 JSON files. `JSONTaskRepository`
uses atomic replacement when saving, so an interrupted write does not leave a
partially written task. The SQLite catalog stores only searchable metadata, the
absolute JSON path, and a SHA-256 digest; it does not duplicate task contents.

`CatalogService.refresh()` rebuilds or reconciles the catalog from the JSON
folder. This also detects tasks edited outside the application because their
content hash is recalculated. Invalid files are reported in the sync result and
are not imported. Execution history is stored separately and remains available
even if a task JSON file is later deleted.

Example:

```python
from pathlib import Path

from create_auto_task.storage.catalog_service import CatalogService
from create_auto_task.storage.json_repository import JSONTaskRepository
from create_auto_task.storage.sqlite_repository import SQLiteRepository

root = Path.home() / ".local/share/create-auto-task"
service = CatalogService(
    JSONTaskRepository(root / "tasks"),
    SQLiteRepository(root / "database/catalog.sqlite3"),
)
result = service.refresh()
print(result)
print(service.list_tasks())
```


## CLI (0.5.0)

The CLI now exposes the task catalog, validation, recording, execution, synchronization, and
execution history. The JSON file remains the source of truth; SQLite is rebuilt
from the task directory when needed.

```bash
create-auto-task list
create-auto-task validate examples/tasks/example.json
create-auto-task record "Open browser" ~/Tasks/open-browser.json
create-auto-task run examples/tasks/example.json
create-auto-task sync
create-auto-task history --limit 20
create-auto-task history --task-id c4c40b2d-1234-4567-8901-123456789abc
```

`run` requires the optional execution dependencies (`pip install -e ".[execution]"`)
and interacts with the real desktop. Review a task with `validate` before running
it. Successful, failed, and cancelled runs are recorded in the local SQLite history.
The CLI and GUI use the same `CatalogService` and `ExecutionEngine`.

## Recorder (0.8.2)

The recorder translates live keyboard/mouse input into CAT
1.0 actions. It captures primary-button clicks (including detected double-clicks),
scrolls, significant pointer movements, printable text, special keys, and common
modifier shortcuts. Small pointer movements are filtered to avoid producing noisy
files; pauses above 250 ms are represented as `WAIT` actions. Right/middle mouse
buttons and drag gestures are not yet represented by CAT 1.0. Escape is reserved as a stop control when held for 3 seconds; it is not recorded as a CAT action. The GUI also offers a stop button as a manual fallback.

Start a recording from the terminal and hold `Escape` for at least 3 seconds to finish and save:

```bash
create-auto-task record "Open browser" ~/Tasks/open-browser.json \
  --description "Launches the browser and opens a page"
```

Recording requires the optional input dependency (`pip install -e ".[execution]"`).
Be careful: keyboard input is recorded, including text typed into password fields.
Do not record credentials or other sensitive information. Review the generated
JSON with `create-auto-task validate` before running it. The platform-independent
`RecorderSession` can also be tested with synthetic events without controlling the
desktop.

## GUI (0.8.2)

The first PySide6 interface uses the same `CatalogService`, `RecorderSession`,
and `ExecutionEngine` as the CLI. It provides a task catalog, task details,
record/pause/resume/stop controls, execution in a worker thread, progress, and
an event log.

Install the GUI dependencies:

```bash
python -m pip install -e ".[all,dev]"
```

Launch it with:

```bash
create-auto-task-gui
```

The GUI is optional. The CLI and core do not require PySide6. Recording and
execution still require the optional `execution` dependencies. The execution
worker keeps the GUI responsive while the desktop automation is running.

## Visual editor (0.8.1)

The optional PySide6 GUI now includes a visual CAT editor. The task list is backed by
`CatalogService`, while the editor manipulates the same `CATTask` model used by the
CLI and execution engine.

Features:

- Create, duplicate and delete CAT tasks.
- Edit task name and description.
- Add and edit allow-listed actions (`CLICK`, `DOUBLE_CLICK`, `MOVE`, `SCROLL`, `KEY`,
  `HOTKEY`, `TYPE`, `WAIT`).
- Remove actions and move them up/down to change execution order.
- Action parameters are validated with the same semantic validator used by the CLI.
- Action IDs are normalized to `1..N` after structural edits.
- Unsaved changes prevent execution until the task is saved.
- Recording remains available from the same window.
- Execution continues in a worker thread so the GUI remains responsive.

Launch it with:

```bash
create-auto-task-gui
```

PySide6 is optional; CLI users do not need the GUI dependency.
