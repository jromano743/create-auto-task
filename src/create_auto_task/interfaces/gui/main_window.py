"""PySide6 desktop interface and visual CAT action editor."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from uuid import uuid4

from create_auto_task.app.config import AppPaths
from create_auto_task.app.events import EventType, ExecutionEvent
from create_auto_task.backends.execution import PyAutoGUIBackend
from create_auto_task.core.engine import ExecutionEngine
from create_auto_task.core.models import Action, CATTask, TaskMetadata, TaskSettings
from create_auto_task.core.parser import dump_task, load_task, parse_task
from create_auto_task.core.validator import COMMAND_REQUIRED_PARAMS, validate_task
from create_auto_task.recorder.listener import PynputRecorder
from create_auto_task.recorder.session import RecorderSession
from create_auto_task.storage.catalog_service import CatalogService
from create_auto_task.storage.json_repository import JSONTaskRepository
from create_auto_task.storage.sqlite_repository import SQLiteRepository


def renumber_actions(actions: list[Action]) -> list[Action]:
    """Return copied actions with stable sequential IDs starting at 1."""
    return [Action(id=index, command=action.command, params=dict(action.params))
            for index, action in enumerate(actions, 1)]


def clone_task(task: CATTask, *, name: str | None = None, new_id: bool = False) -> CATTask:
    """Create an editable copy without sharing mutable action dictionaries."""
    data = task.model_dump(mode="python")
    data["actions"] = [a.model_dump(mode="python") for a in renumber_actions(task.actions)]
    if name is not None:
        data["metadata"]["name"] = name
    if new_id:
        data["id"] = uuid4()
        data["metadata"]["created_at"] = datetime.now(timezone.utc)
    return CATTask.model_validate(data)


def build_action(command: str, params: dict) -> Action:
    """Build and validate a single CAT action for the visual editor."""
    command = command.upper().strip()
    if command not in COMMAND_REQUIRED_PARAMS:
        raise ValueError(f"Unsupported command: {command}")
    return Action(id=1, command=command, params=params)


class MainWindow:
    """Desktop UI; PySide6 remains an optional dependency."""

    def __new__(cls):
        from PySide6.QtWidgets import QMainWindow

        class _Window(QMainWindow):
            def __init__(self):
                super().__init__()
                self.setWindowTitle("Create Auto Task — CAT Editor")
                self.resize(1280, 780)
                self.service = _build_service()
                self.recorder = None
                self.worker = None
                self.cancel_event = None
                self.current_task: CATTask | None = None
                self._task_rows: list[dict] = []
                self._dirty = False
                self._build_ui()
                self.refresh_tasks()

            def _build_ui(self):
                from PySide6.QtCore import Qt
                from PySide6.QtWidgets import (
                    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget,
                    QPushButton, QPlainTextEdit, QProgressBar, QSplitter,
                    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
                )

                central = QWidget()
                root = QVBoxLayout(central)
                toolbar = QHBoxLayout()
                self.new_btn = QPushButton("＋ Nueva")
                self.record_btn = QPushButton("● Grabar")
                self.stop_record_btn = QPushButton("■ Detener grabación")
                self.stop_record_btn.setEnabled(False)
                self.run_btn = QPushButton("▶ Ejecutar")
                self.save_btn = QPushButton("💾 Guardar")
                self.delete_btn = QPushButton("🗑 Eliminar")
                self.duplicate_btn = QPushButton("⧉ Duplicar")
                self.refresh_btn = QPushButton("↻ Actualizar")
                for button in (self.new_btn, self.record_btn, self.stop_record_btn, self.run_btn,
                               self.save_btn, self.delete_btn, self.duplicate_btn, self.refresh_btn):
                    toolbar.addWidget(button)
                toolbar.addStretch()
                root.addLayout(toolbar)

                splitter = QSplitter(Qt.Horizontal)
                left = QWidget()
                left_layout = QVBoxLayout(left)
                left_layout.addWidget(QLabel("TAREAS"))
                self.task_list = QListWidget()
                left_layout.addWidget(self.task_list)
                splitter.addWidget(left)

                right = QWidget()
                right_layout = QVBoxLayout(right)
                details = QGroupBox("Propiedades")
                form = QFormLayout(details)
                self.name_edit = __import__("PySide6.QtWidgets", fromlist=["QLineEdit"]).QLineEdit()
                self.description_edit = QPlainTextEdit()
                self.description_edit.setMaximumHeight(70)
                self.id_label = QLabel("—")
                self.count_label = QLabel("0")
                form.addRow("Nombre:", self.name_edit)
                form.addRow("Descripción:", self.description_edit)
                form.addRow("ID:", self.id_label)
                form.addRow("Acciones:", self.count_label)
                right_layout.addWidget(details)

                action_box = QGroupBox("Acciones CAT")
                action_layout = QVBoxLayout(action_box)
                action_toolbar = QHBoxLayout()
                self.add_action_btn = QPushButton("＋ Acción")
                self.edit_action_btn = QPushButton("✎ Editar")
                self.remove_action_btn = QPushButton("− Quitar")
                self.up_btn = QPushButton("↑")
                self.down_btn = QPushButton("↓")
                for button in (self.add_action_btn, self.edit_action_btn, self.remove_action_btn,
                               self.up_btn, self.down_btn):
                    action_toolbar.addWidget(button)
                action_toolbar.addStretch()
                action_layout.addLayout(action_toolbar)
                self.action_table = QTableWidget(0, 3)
                self.action_table.setHorizontalHeaderLabels(["#", "COMANDO", "PARÁMETROS"])
                self.action_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
                self.action_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
                self.action_table.horizontalHeader().setStretchLastSection(True)
                action_layout.addWidget(self.action_table)
                right_layout.addWidget(action_box, 1)

                self.progress = QProgressBar()
                self.progress.setRange(0, 100)
                right_layout.addWidget(self.progress)
                right_layout.addWidget(QLabel("Eventos / ejecución"))
                self.events = QPlainTextEdit()
                self.events.setReadOnly(True)
                right_layout.addWidget(self.events, 1)
                splitter.addWidget(right)
                splitter.setSizes([300, 980])
                root.addWidget(splitter)
                self.statusBar().showMessage("Listo")
                self.setCentralWidget(central)

                self.new_btn.clicked.connect(self.new_task)
                self.record_btn.clicked.connect(self.start_recording)
                self.stop_record_btn.clicked.connect(self.stop_recording)
                self.run_btn.clicked.connect(self.run_selected)
                self.save_btn.clicked.connect(self.save_current)
                self.delete_btn.clicked.connect(self.delete_selected)
                self.duplicate_btn.clicked.connect(self.duplicate_selected)
                self.refresh_btn.clicked.connect(self.refresh_tasks)
                self.task_list.currentRowChanged.connect(self.show_selected)
                self.name_edit.textChanged.connect(self._mark_dirty)
                self.description_edit.textChanged.connect(self._mark_dirty)
                self.add_action_btn.clicked.connect(self.add_action)
                self.edit_action_btn.clicked.connect(self.edit_action)
                self.remove_action_btn.clicked.connect(self.remove_action)
                self.up_btn.clicked.connect(lambda: self.move_action(-1))
                self.down_btn.clicked.connect(lambda: self.move_action(1))
                self.action_table.itemDoubleClicked.connect(lambda *_: self.edit_action())
                self.action_table.itemSelectionChanged.connect(self._update_editor_state)
                from PySide6.QtCore import QTimer
                self._recording_poll = QTimer(self)
                self._recording_poll.setInterval(100)
                self._recording_poll.timeout.connect(self._check_recording_stop)
                self._update_editor_state()

            def _mark_dirty(self):
                if self.current_task is not None:
                    self._dirty = True
                    self.statusBar().showMessage("Cambios sin guardar")

            def _update_editor_state(self):
                has_task = self.current_task is not None
                has_action = has_task and self.action_table.currentRow() >= 0
                self.save_btn.setEnabled(has_task and self._dirty)
                recording = self.recorder is not None
                self.record_btn.setEnabled(not recording and self.worker is None)
                self.stop_record_btn.setEnabled(recording)
                self.delete_btn.setEnabled(has_task and self.worker is None and self.recorder is None)
                self.duplicate_btn.setEnabled(has_task and self.worker is None and self.recorder is None)
                self.add_action_btn.setEnabled(has_task and self.worker is None and self.recorder is None)
                self.edit_action_btn.setEnabled(has_action and self.worker is None and self.recorder is None)
                self.remove_action_btn.setEnabled(has_action and self.worker is None and self.recorder is None)
                self.up_btn.setEnabled(has_action and self.action_table.currentRow() > 0)
                self.down_btn.setEnabled(has_action and self.action_table.currentRow() < self.action_table.rowCount() - 1)
                self.run_btn.setEnabled(has_task and not self._dirty and self.worker is None and self.recorder is None)

            def refresh_tasks(self):
                result = self.service.refresh()
                self._task_rows = self.service.list_tasks()
                selected_id = str(self.current_task.id) if self.current_task else None
                self.task_list.blockSignals(True)
                self.task_list.clear()
                selected_row = -1
                for index, item in enumerate(self._task_rows):
                    self.task_list.addItem(item["name"])
                    if item["task_id"] == selected_id:
                        selected_row = index
                self.task_list.blockSignals(False)
                if selected_row >= 0:
                    self.task_list.setCurrentRow(selected_row)
                elif self._task_rows:
                    self.task_list.setCurrentRow(0)
                else:
                    self._set_current_task(None)
                if result.errors:
                    self._log("WARN: " + " | ".join(result.errors))
                self.statusBar().showMessage(f"{len(self._task_rows)} tarea(s) en catálogo")

            def _set_current_task(self, task: CATTask | None):
                self.current_task = task
                self._dirty = False
                self.name_edit.blockSignals(True)
                self.description_edit.blockSignals(True)
                self.name_edit.setText(task.metadata.name if task else "")
                self.description_edit.setPlainText(task.metadata.description if task else "")
                self.name_edit.blockSignals(False)
                self.description_edit.blockSignals(False)
                self.id_label.setText(str(task.id) if task else "—")
                self._populate_actions()
                self._update_editor_state()

            def show_selected(self, row: int):
                if row < 0 or row >= len(self._task_rows):
                    self._set_current_task(None)
                    return
                try:
                    self._set_current_task(load_task(self._task_rows[row]["file_path"]))
                except Exception as exc:
                    self._set_current_task(None)
                    self._log(f"ERROR: {exc}")

            def _populate_actions(self, select_row: int = -1):
                from PySide6.QtWidgets import QTableWidgetItem
                self.action_table.setRowCount(0)
                if not self.current_task:
                    self.count_label.setText("0")
                    return
                for row, action in enumerate(self.current_task.actions):
                    self.action_table.insertRow(row)
                    self.action_table.setItem(row, 0, QTableWidgetItem(str(action.id)))
                    self.action_table.setItem(row, 1, QTableWidgetItem(action.command))
                    self.action_table.setItem(row, 2, QTableWidgetItem(_format_params(action.params)))
                self.count_label.setText(str(len(self.current_task.actions)))
                if 0 <= select_row < self.action_table.rowCount():
                    self.action_table.selectRow(select_row)
                self._update_editor_state()

            def _replace_actions(self, actions: list[Action], select_row: int = -1):
                if not self.current_task:
                    return
                self.current_task = clone_task(self.current_task)
                data = self.current_task.model_dump(mode="python")
                data["actions"] = [a.model_dump(mode="python") for a in renumber_actions(actions)]
                self.current_task = CATTask.model_validate(data)
                self._dirty = True
                self._populate_actions(select_row)
                self.statusBar().showMessage("Cambios sin guardar")

            def _ask_action(self, existing: Action | None = None):
                return _ActionDialog(self, existing).exec_and_get()

            def add_action(self):
                if not self.current_task:
                    return
                action = self._ask_action()
                if action:
                    actions = list(self.current_task.actions) + [action]
                    self._replace_actions(actions, len(actions) - 1)

            def edit_action(self):
                row = self.action_table.currentRow()
                if not self.current_task or row < 0:
                    return
                action = self._ask_action(self.current_task.actions[row])
                if action:
                    actions = list(self.current_task.actions)
                    actions[row] = action
                    self._replace_actions(actions, row)

            def remove_action(self):
                row = self.action_table.currentRow()
                if not self.current_task or row < 0:
                    return
                from PySide6.QtWidgets import QMessageBox
                if QMessageBox.question(self, "Quitar acción", f"¿Eliminar la acción #{row + 1}?") != QMessageBox.StandardButton.Yes:
                    return
                actions = list(self.current_task.actions)
                actions.pop(row)
                if not actions:
                    QMessageBox.warning(self, "Acción requerida", "Una tarea CAT debe tener al menos una acción.")
                    return
                self._replace_actions(actions, min(row, len(actions) - 1))

            def move_action(self, delta: int):
                row = self.action_table.currentRow()
                if not self.current_task or row < 0:
                    return
                target = row + delta
                if target < 0 or target >= len(self.current_task.actions):
                    return
                actions = list(self.current_task.actions)
                actions[row], actions[target] = actions[target], actions[row]
                self._replace_actions(actions, target)

            def save_current(self):
                if not self.current_task:
                    return
                try:
                    data = self.current_task.model_dump(mode="python")
                    data["metadata"]["name"] = self.name_edit.text().strip()
                    data["metadata"]["description"] = self.description_edit.toPlainText()
                    task = CATTask.model_validate(data)
                    validate_task(task)
                    path = self.service.save_task(task)
                    self._set_current_task(task)
                    self.refresh_tasks()
                    self.statusBar().showMessage(f"Guardado: {path}")
                except Exception as exc:
                    self._log(f"ERROR al guardar: {exc}")

            def new_task(self):
                from PySide6.QtWidgets import QInputDialog
                name, ok = QInputDialog.getText(self, "Nueva tarea", "Nombre:")
                if not ok or not name.strip():
                    return
                description, ok = QInputDialog.getText(self, "Nueva tarea", "Descripción (opcional):")
                if not ok:
                    return
                task = CATTask(
                    format="CAT", version="1.0", id=uuid4(),
                    metadata=TaskMetadata(name=name.strip(), description=description, created_at=datetime.now(timezone.utc)),
                    settings=TaskSettings(),
                    actions=[Action(id=1, command="WAIT", params={"seconds": 1.0})],
                )
                self.service.save_task(task)
                self.refresh_tasks()
                self._select_task_id(task.id)
                self._log(f"Nueva tarea creada: {task.metadata.name}")

            def duplicate_selected(self):
                if not self.current_task:
                    return
                from PySide6.QtWidgets import QInputDialog
                name, ok = QInputDialog.getText(self, "Duplicar tarea", "Nombre:", text=self.current_task.metadata.name + " (copia)")
                if not ok or not name.strip():
                    return
                task = clone_task(self.current_task, name=name.strip(), new_id=True)
                self.service.save_task(task)
                self.refresh_tasks()
                self._select_task_id(task.id)
                self._log(f"Tarea duplicada: {task.metadata.name}")

            def delete_selected(self):
                if not self.current_task:
                    return
                from PySide6.QtWidgets import QMessageBox
                if QMessageBox.question(self, "Eliminar tarea", f"¿Eliminar '{self.current_task.metadata.name}'?") != QMessageBox.StandardButton.Yes:
                    return
                task_id = str(self.current_task.id)
                if self.service.delete_task(task_id):
                    self._set_current_task(None)
                    self.refresh_tasks()
                    self._log(f"Tarea eliminada: {task_id}")

            def _select_task_id(self, task_id):
                for row, item in enumerate(self._task_rows):
                    if item["task_id"] == str(task_id):
                        self.task_list.setCurrentRow(row)
                        return

            def start_recording(self):
                from PySide6.QtWidgets import QInputDialog
                name, ok = QInputDialog.getText(self, "Nueva grabación", "Nombre de la tarea:")
                if not ok or not name.strip():
                    return
                session = RecorderSession(name)
                try:
                    recorder = PynputRecorder(session)
                    recorder.start()
                except Exception as exc:
                    self._log(f"ERROR: {exc}")
                    return
                self.recorder = recorder
                self.events.clear()
                self._log(f"Grabando: {name}. Mantené Escape durante 3 segundos para detener y guardar.")
                self._update_editor_state()
                self._recording_poll.start()
                self.statusBar().showMessage("GRABANDO — mantené Escape durante 3 segundos para detener y guardar")

            def _check_recording_stop(self):
                if self.recorder is not None and self.recorder.stop_requested.is_set():
                    self.stop_recording()

            def stop_recording(self):
                if not self.recorder:
                    return
                self._recording_poll.stop()
                try:
                    task = self.recorder.stop()
                    path = self.service.save_task(task)
                    self._log(f"Grabación guardada: {path}")
                except Exception as exc:
                    self._log(f"ERROR al guardar grabación: {exc}")
                finally:
                    self.recorder = None
                    self.refresh_tasks()
                    self._update_editor_state()
                    self.statusBar().showMessage("Grabación finalizada")

            def run_selected(self):
                if not self.current_task or self._dirty:
                    self._log("Guardá los cambios antes de ejecutar.")
                    return
                task = self.current_task
                try:
                    validate_task(task)
                except Exception as exc:
                    self._log(f"ERROR de validación: {exc}")
                    return
                self.events.clear()
                self.progress.setValue(0)
                self.cancel_event = Event()
                self._update_editor_state()
                self.worker = _ExecutionWorker(task, self.cancel_event, self.service)
                self.worker.event.connect(self.on_execution_event)
                self.worker.finished.connect(self.on_execution_finished)
                self.worker.start()
                self.statusBar().showMessage("Ejecutando…")

            def on_execution_event(self, event: ExecutionEvent):
                self._log(f"[{event.type}] {event.message}")
                if event.total:
                    self.progress.setValue(int(event.current * 100 / event.total))

            def on_execution_finished(self, status: str, message: str):
                self._log(message)
                self.worker = None
                self.cancel_event = None
                self.refresh_tasks()
                self._update_editor_state()
                self.statusBar().showMessage(status)

            def _log(self, message: str):
                self.events.appendPlainText(message)

            def closeEvent(self, event):
                if self.worker is not None:
                    from PySide6.QtWidgets import QMessageBox
                    answer = QMessageBox.question(self, "Ejecución activa", "¿Cancelar la ejecución y salir?")
                    if answer != QMessageBox.StandardButton.Yes:
                        event.ignore()
                        return
                    self.cancel_event.set()
                    self.worker.wait(3000)
                if self.recorder is not None:
                    from PySide6.QtWidgets import QMessageBox
                    answer = QMessageBox.question(self, "Grabación activa", "¿Detener la grabación y salir?")
                    if answer != QMessageBox.StandardButton.Yes:
                        event.ignore()
                        return
                    try:
                        self.recorder.stop()
                    except Exception:
                        pass
                event.accept()

        return _Window()


def _format_params(params: dict) -> str:
    import json
    return json.dumps(params, ensure_ascii=False, sort_keys=True)


def _build_service() -> CatalogService:
    paths = AppPaths.default()
    paths.ensure_directories()
    return CatalogService(JSONTaskRepository(paths.tasks), SQLiteRepository(paths.database / "catalog.sqlite3"))


class _ActionDialog:
    """Small command-aware dialog; kept behind the optional GUI dependency."""
    def __init__(self, parent, existing: Action | None = None):
        from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox
        self.dialog = QDialog(parent)
        self.dialog.setWindowTitle("Editar acción" if existing else "Nueva acción")
        self.form = QFormLayout(self.dialog)
        self.command = QComboBox()
        self.command.addItems(sorted(COMMAND_REQUIRED_PARAMS))
        self.form.addRow("Comando:", self.command)
        self.fields = {}
        for key in ("x", "y", "amount", "seconds", "key", "keys", "text"):
            if key in {"x", "y", "amount"}:
                widget = QSpinBox(); widget.setRange(-1000000, 1000000)
            elif key == "seconds":
                widget = QDoubleSpinBox(); widget.setRange(0, 36000); widget.setDecimals(3); widget.setSingleStep(0.1)
            else:
                widget = QLineEdit()
            self.fields[key] = widget
            self.form.addRow(f"{key}:", widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.form.addRow(buttons)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.dialog.reject)
        self.command.currentTextChanged.connect(self._update_fields)
        if existing:
            self.command.setCurrentText(existing.command)
            for key, value in existing.params.items():
                if key == "keys": value = ", ".join(value)
                self.fields[key].setValue(value) if key in {"x", "y", "amount", "seconds"} else self.fields[key].setText(str(value))
        self._update_fields(self.command.currentText())
        self.result = None

    def _update_fields(self, command: str):
        required = COMMAND_REQUIRED_PARAMS[command]
        for key, widget in self.fields.items():
            widget.setVisible(key in required)
            label = self.form.labelForField(widget)
            if label:
                label.setVisible(key in required)

    def _accept(self):
        command = self.command.currentText()
        required = COMMAND_REQUIRED_PARAMS[command]
        params = {}
        for key in required:
            widget = self.fields[key]
            if key in {"x", "y", "amount"}:
                params[key] = widget.value()
            elif key == "seconds":
                params[key] = widget.value()
            elif key == "keys":
                params[key] = [part.strip().upper() for part in widget.text().split(",") if part.strip()]
            else:
                params[key] = widget.text()
        try:
            action = build_action(command, params)
            # Validate through the same semantic rules used for complete tasks.
            probe = CATTask(format="CAT", version="1.0", id=uuid4(),
                metadata=TaskMetadata(name="probe", created_at=datetime.now(timezone.utc)),
                actions=[action])
            validate_task(probe)
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self.dialog, "Acción inválida", str(exc))
            return
        self.result = action
        self.dialog.accept()

    def exec_and_get(self):
        return self.result if self.dialog.exec() else None


class _ExecutionWorker:
    """QThread wrapper created lazily so importing this module needs no Qt."""
    def __new__(cls, task, cancel_event, service):
        from PySide6.QtCore import QThread, Signal

        class Worker(QThread):
            event = Signal(object)
            finished = Signal(str, str)

            def __init__(self, task, cancel_event, service):
                super().__init__()
                self.task, self.cancel_event, self.service = task, cancel_event, service

            def run(self):
                started = datetime.now(timezone.utc).isoformat()
                completed, failed, status, error = 0, [], "FAILED", None
                try:
                    backend = PyAutoGUIBackend(fail_safe=self.task.settings.fail_safe, speed=self.task.settings.speed)
                    result = ExecutionEngine(backend).run(self.task, on_event=self.event.emit, cancel_event=self.cancel_event)
                    completed, failed = result.completed_actions, list(result.failed_actions)
                    status = "CANCELLED" if result.cancelled else ("FAILED" if failed else "COMPLETED")
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                finally:
                    self.service.record_execution(task_id=str(self.task.id), task_name=self.task.metadata.name,
                        started_at=started, finished_at=datetime.now(timezone.utc).isoformat(), status=status,
                        completed_actions=completed, total_actions=len(self.task.actions), failed_actions=failed, error=error)
                    self.finished.emit(status, error or f"Resultado: {status} ({completed}/{len(self.task.actions)})")

        return Worker(task, cancel_event, service)
