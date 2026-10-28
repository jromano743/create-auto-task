"""PySide6 application entry point for Create Auto Task."""
from __future__ import annotations


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        raise RuntimeError(
            "The GUI requires PySide6; install create-auto-task[gui] or create-auto-task[all]"
        ) from exc

    from create_auto_task.interfaces.gui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Create Auto Task")
    app.setApplicationVersion("0.8.0")
    window = MainWindow()
    window.show()
    return app.exec()
