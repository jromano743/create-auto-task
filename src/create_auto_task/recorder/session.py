"""Platform-independent recording session and event-to-CAT translation."""
from __future__ import annotations

from datetime import datetime, timezone
from time import monotonic
from uuid import uuid4

from create_auto_task.core.models import CATTask


_MODIFIERS = {"ctrl", "ctrl_l", "ctrl_r", "alt", "alt_l", "alt_r", "shift", "shift_l", "shift_r", "cmd", "cmd_l", "cmd_r"}
_KEY_ALIASES = {
    "Key.enter": "ENTER", "Key.tab": "TAB", "Key.space": "SPACE",
    "Key.backspace": "BACKSPACE", "Key.delete": "DELETE", "Key.esc": "ESC",
    "Key.up": "UP", "Key.down": "DOWN", "Key.left": "LEFT", "Key.right": "RIGHT",
    "Key.home": "HOME", "Key.end": "END", "Key.page_up": "PAGEUP", "Key.page_down": "PAGEDOWN",
}


class RecorderSession:
    """Collect normalized desktop events without depending on pynput or a GUI."""

    def __init__(self, name: str, description: str = "", *, wait_threshold: float = 0.25) -> None:
        if not name.strip():
            raise ValueError("Task name must not be blank")
        if wait_threshold < 0:
            raise ValueError("wait_threshold must be >= 0")
        self.name = name.strip()
        self.description = description
        self.wait_threshold = wait_threshold
        self.actions: list[dict] = []
        self._started_at: float | None = None
        self._last_event_at: float | None = None
        self._pressed_modifiers: set[str] = set()
        self._pending_hotkey: list[str] = []
        self._last_move: tuple[int, int] | None = None
        self._last_click: tuple[int, int, float] | None = None
        self._state = "idle"

    @property
    def state(self) -> str:
        return self._state

    def start(self) -> None:
        if self._state != "idle":
            raise RuntimeError("A recording session can only be started once")
        self._started_at = self._last_event_at = monotonic()
        self._state = "recording"

    def pause(self) -> None:
        if self._state != "recording":
            raise RuntimeError("Only an active recording can be paused")
        self._flush_hotkey()
        self._state = "paused"
        self._last_event_at = None

    def resume(self) -> None:
        if self._state != "paused":
            raise RuntimeError("Only a paused recording can be resumed")
        self._state = "recording"
        self._last_event_at = monotonic()

    def stop(self) -> CATTask:
        if self._state not in {"recording", "paused"}:
            raise RuntimeError("No active recording to stop")
        self._flush_hotkey()
        self._state = "stopped"
        if not self.actions:
            raise ValueError("Recording is empty; no CAT task was created")
        return self.to_task()

    def _before_action(self) -> None:
        if self._state != "recording":
            return
        now = monotonic()
        if self._last_event_at is not None:
            elapsed = now - self._last_event_at
            if elapsed >= self.wait_threshold:
                self._append("WAIT", {"seconds": round(elapsed, 3)})
        self._last_event_at = now

    def _append(self, command: str, params: dict) -> None:
        self.actions.append({"id": len(self.actions) + 1, "command": command, "params": params})

    def move(self, x: int, y: int, *, min_distance: int = 25) -> None:
        if self._state != "recording": return
        point = (int(x), int(y))
        if self._last_move is not None:
            dx, dy = point[0] - self._last_move[0], point[1] - self._last_move[1]
            if dx * dx + dy * dy < min_distance * min_distance:
                return
        self._flush_hotkey(); self._before_action()
        self._append("MOVE", {"x": point[0], "y": point[1]})
        self._last_move = point

    def click(self, x: int, y: int, button: str = "left", count: int = 1) -> None:
        if self._state != "recording" or button != "left": return
        self._flush_hotkey()
        now = monotonic()
        point = (int(x), int(y))
        if count >= 2 or (self._last_click and self._last_click[:2] == point
                          and now - self._last_click[2] <= 0.35
                          and self.actions and self.actions[-1]["command"] == "CLICK"
                          and self.actions[-1]["params"] == {"x": point[0], "y": point[1]}):
            if self.actions and self.actions[-1]["command"] == "CLICK":
                self.actions[-1]["command"] = "DOUBLE_CLICK"
            else:
                self._before_action()
                self._append("DOUBLE_CLICK", {"x": point[0], "y": point[1]})
            self._last_click = None
            return
        self._before_action()
        self._append("CLICK", {"x": point[0], "y": point[1]})
        self._last_click = (point[0], point[1], now)

    def scroll(self, amount: int) -> None:
        if self._state != "recording" or amount == 0: return
        self._flush_hotkey(); self._before_action()
        self._append("SCROLL", {"amount": int(amount)})

    def key_press(self, key: str) -> None:
        if self._state != "recording": return
        raw = str(key)
        normalized = raw.lower().replace("key.", "")
        if normalized in _MODIFIERS:
            self._pressed_modifiers.add(normalized)
            return
        non_shift_modifiers = self._pressed_modifiers - {"shift", "shift_l", "shift_r"}
        if len(raw) == 1 and raw.isprintable() and not non_shift_modifiers:
            self._flush_hotkey(); self._before_action()
            if self.actions and self.actions[-1]["command"] == "TYPE":
                self.actions[-1]["params"]["text"] += raw
            else:
                self._append("TYPE", {"text": raw})
            return
        self._before_action()
        key_name = _KEY_ALIASES.get(raw, raw.upper().replace("KEY.", ""))
        if self._pressed_modifiers:
            self._pending_hotkey = sorted(self._pressed_modifiers) + [key_name]
        else:
            self._flush_hotkey()
            self._before_action()
            self._append("KEY", {"key": key_name})

    def key_release(self, key: str) -> None:
        raw = str(key).lower().replace("key.", "")
        if raw in _MODIFIERS:
            self._pressed_modifiers.discard(raw)

    def _flush_hotkey(self) -> None:
        if self._pending_hotkey:
            # Normalize modifier aliases and retain deterministic modifier order.
            aliases = {"ctrl_l": "CTRL", "ctrl_r": "CTRL", "ctrl": "CTRL", "alt_l": "ALT", "alt_r": "ALT", "alt": "ALT", "shift_l": "SHIFT", "shift_r": "SHIFT", "shift": "SHIFT", "cmd_l": "CMD", "cmd_r": "CMD", "cmd": "CMD"}
            normalized = {aliases.get(k, k.upper()) for k in self._pending_hotkey}
            keys = [key for key in ("CTRL", "ALT", "SHIFT", "CMD") if key in normalized]
            keys.extend(k.upper() for k in self._pending_hotkey if k not in aliases)
            self._append("HOTKEY", {"keys": keys})
            self._pending_hotkey = []

    def to_task(self) -> CATTask:
        if not self.actions:
            raise ValueError("Cannot create a CAT task without actions")
        return CATTask.model_validate({
            "format": "CAT", "version": "1.0", "id": str(uuid4()),
            "metadata": {"name": self.name, "description": self.description,
                         "created_at": datetime.now(timezone.utc).isoformat()},
            "settings": {"error_policy": "STOP", "fail_safe": True, "speed": 1.0},
            "actions": self.actions,
        })
