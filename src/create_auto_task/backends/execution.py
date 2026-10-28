"""Execution backend protocol and optional PyAutoGUI implementation."""
from typing import Protocol


class ExecutionBackend(Protocol):
    def click(self, x: int | float, y: int | float) -> None: ...
    def double_click(self, x: int | float, y: int | float) -> None: ...
    def move(self, x: int | float, y: int | float) -> None: ...
    def scroll(self, amount: int | float) -> None: ...
    def press(self, key: str) -> None: ...
    def hotkey(self, keys: list[str]) -> None: ...
    def write(self, text: str) -> None: ...
    def wait(self, seconds: int | float) -> None: ...


class PyAutoGUIBackend:
    """Thin adapter; imports PyAutoGUI only when instantiated."""

    def __init__(self, *, fail_safe: bool = True, speed: float = 1.0) -> None:
        try:
            import pyautogui
        except ImportError as exc:
            raise RuntimeError("Execution requires PyAutoGUI; install create-auto-task[execution]") from exc
        self._gui = pyautogui
        self._gui.FAILSAFE = fail_safe
        self._speed = speed

    def click(self, x: int | float, y: int | float) -> None:
        self._gui.click(x=x, y=y)

    def double_click(self, x: int | float, y: int | float) -> None:
        self._gui.doubleClick(x=x, y=y)

    def move(self, x: int | float, y: int | float) -> None:
        self._gui.moveTo(x=x, y=y, duration=0.1 / self._speed)

    def scroll(self, amount: int | float) -> None:
        self._gui.scroll(amount)

    def press(self, key: str) -> None:
        self._gui.press(key.lower())

    def hotkey(self, keys: list[str]) -> None:
        self._gui.hotkey(*(key.lower() for key in keys))

    def write(self, text: str) -> None:
        self._gui.write(text, interval=0.01 / self._speed)

    def wait(self, seconds: int | float) -> None:
        import time
        time.sleep(seconds / self._speed)
