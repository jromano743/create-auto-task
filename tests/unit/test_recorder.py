from create_auto_task.core.validator import validate_task
from create_auto_task.recorder.session import RecorderSession


def active_session():
    session = RecorderSession("Recorded task", wait_threshold=999)
    session.start()
    return session


def test_records_click_scroll_and_typed_text():
    session = active_session()
    session.click(120, 240)
    session.scroll(-3)
    session.key_press("h")
    session.key_press("i")
    task = session.stop()
    validate_task(task)
    assert [a.command for a in task.actions] == ["CLICK", "SCROLL", "TYPE"]
    assert task.actions[-1].params == {"text": "hi"}


def test_records_hotkey_and_special_key():
    session = active_session()
    session.key_press("Key.ctrl_l")
    session.key_press("a")
    session.key_release("Key.ctrl_l")
    session.key_press("Key.enter")
    task = session.stop()
    validate_task(task)
    assert task.actions[0].command == "HOTKEY"
    assert task.actions[0].params["keys"] == ["CTRL", "A"]
    assert task.actions[1].params == {"key": "ENTER"}


def test_pause_ignores_events_and_resume_continues():
    session = active_session()
    session.click(1, 2)
    session.pause()
    session.click(3, 4)
    session.resume()
    session.click(5, 6)
    task = session.stop()
    assert [a.params for a in task.actions if a.command == "CLICK"] == [
        {"x": 1, "y": 2}, {"x": 5, "y": 6}
    ]


def test_empty_recording_cannot_be_saved():
    session = active_session()
    try:
        session.stop()
    except ValueError as exc:
        assert "empty" in str(exc).lower()
    else:
        raise AssertionError("Expected empty recording to be rejected")


def test_records_significant_pointer_moves_and_double_clicks():
    session = active_session()
    session.move(10, 10)
    session.move(12, 12)  # below movement threshold
    session.move(80, 90)
    session.click(80, 90)
    session.click(80, 90)  # same point within the double-click window
    task = session.stop()
    validate_task(task)
    assert [a.command for a in task.actions] == ["MOVE", "MOVE", "DOUBLE_CLICK"]


def test_shifted_printable_key_is_text_not_hotkey():
    session = active_session()
    session.key_press("Key.shift")
    session.key_press("A")
    session.key_release("Key.shift")
    task = session.stop()
    assert len(task.actions) == 1
    assert task.actions[0].command == "TYPE"
    assert task.actions[0].params == {"text": "A"}


def test_escape_is_recording_control_not_cat_action():
    from create_auto_task.recorder.listener import PynputRecorder

    session = active_session()
    recorder = PynputRecorder(session)
    recorder._on_key_press("Key.esc")
    recorder._on_key_release("Key.esc")
    session.key_press("x")
    task = session.stop()
    assert [action.command for action in task.actions] == ["TYPE"]
    assert task.actions[0].params == {"text": "x"}
    assert recorder.stop_requested.is_set() is False


def test_escape_hold_requests_stop():
    from create_auto_task.recorder.listener import PynputRecorder

    recorder = PynputRecorder(active_session(), escape_hold_seconds=3)
    recorder._request_stop()
    assert recorder.stop_requested.is_set()
