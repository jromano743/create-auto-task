"""Optional pynput adapter for desktop input capture."""
from __future__ import annotations

from threading import Event, Timer


class PynputRecorder:
    """Attach pynput listeners and stop after Escape is held for the configured duration."""

    def __init__(self, session, *, escape_hold_seconds: float = 3.0) -> None:
        if escape_hold_seconds <= 0:
            raise ValueError("escape_hold_seconds must be positive")
        self.session = session
        self.escape_hold_seconds = escape_hold_seconds
        self._mouse = None
        self._keyboard = None
        self._escape_timer: Timer | None = None
        self.stop_requested = Event()
        self._started = False

    def start(self) -> None:
        try:
            from pynput import keyboard, mouse
        except ImportError as exc:
            raise RuntimeError("Recording requires pynput; install create-auto-task[execution]") from exc
        self.session.start()
        self.stop_requested.clear()
        self._started = True
        self._mouse = mouse.Listener(
            on_click=lambda x, y, button, pressed: self.session.click(x, y, str(button).split(".")[-1]) if pressed else None,
            on_scroll=lambda x, y, dx, dy: self.session.scroll(dy),
            on_move=lambda x, y: self.session.move(x, y),
        )
        self._keyboard = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._mouse.start()
        self._keyboard.start()

    def _on_key_press(self, key) -> None:
        if str(key) == "Key.esc":
            if self._escape_timer is None:
                self._escape_timer = Timer(self.escape_hold_seconds, self._request_stop)
                self._escape_timer.daemon = True
                self._escape_timer.start()
            return  # Escape is a recording control, not a CAT action.
        self.session.key_press(getattr(key, "char", None) or str(key))

    def _on_key_release(self, key) -> None:
        if str(key) == "Key.esc":
            if self._escape_timer is not None:
                self._escape_timer.cancel()
                self._escape_timer = None
            return
        self.session.key_release(str(key))

    def _request_stop(self) -> None:
        self.stop_requested.set()
        # Stop listening immediately; the CLI/UI will finalize and save the session.
        for listener in (self._mouse, self._keyboard):
            if listener is not None:
                listener.stop()

    def wait(self) -> None:
        """Block until Escape has been held long enough to request stopping."""
        self.stop_requested.wait()

    def stop(self):
        if self._escape_timer is not None:
            self._escape_timer.cancel()
            self._escape_timer = None
        for listener in (self._mouse, self._keyboard):
            if listener is not None:
                listener.stop()
                listener.join(timeout=2)
        self._started = False
        return self.session.stop()

    def pause(self) -> None:
        self.session.pause()

    def resume(self) -> None:
        self.session.resume()
