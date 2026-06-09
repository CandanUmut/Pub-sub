"""Unit tests for the GUI log bus (no Tk / no network needed)."""

import logging
import queue

from gui import logbus


def test_emit_and_snapshot():
    bus = logbus.LogBus(maxlen=10)
    bus.emit("hello")
    bus.emit("world")
    assert bus.snapshot() == ["hello", "world"]


def test_maxlen_evicts_oldest():
    bus = logbus.LogBus(maxlen=3)
    for i in range(5):
        bus.emit(str(i))
    assert bus.snapshot() == ["2", "3", "4"]


def test_listener_receives_new_lines():
    bus = logbus.LogBus()
    q: "queue.Queue[str]" = queue.Queue()
    bus.add_listener(q)
    bus.emit("a")
    bus.emit("b")
    assert q.get_nowait() == "a"
    assert q.get_nowait() == "b"


def test_remove_listener_stops_delivery():
    bus = logbus.LogBus()
    q: "queue.Queue[str]" = queue.Queue()
    bus.add_listener(q)
    bus.remove_listener(q)
    bus.emit("x")
    assert q.empty()


def test_clear_empties_history():
    bus = logbus.LogBus()
    bus.emit("x")
    bus.clear()
    assert bus.snapshot() == []


def test_get_logger_routes_to_shared_bus():
    logbus.setup_logging(level=logging.INFO)
    before = len(logbus.LOG_BUS.snapshot())
    logbus.get_logger("unittest").info("traceable message")
    after = logbus.LOG_BUS.snapshot()
    assert len(after) == before + 1
    assert "traceable message" in after[-1]
    assert "unittest" in after[-1]
