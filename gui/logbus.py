"""Central log bus + Python logging setup for the GUI.

Every panel and the network layer log through `get_logger(component)`. Records
are formatted into single lines and fanned out to (a) the console and (b) any
open log windows via thread-safe listener queues. Logging happens from both the
Tk main thread and background daemon threads, so the bus is lock-guarded.
"""

import logging
import threading
import time
from collections import deque

_MAXLEN = 2000


class LogBus:
    """Thread-safe in-memory log store with live listeners.

    `emit` may be called from any thread. Listeners are `queue.Queue`s owned by
    log windows; each window drains its own queue on the Tk main thread.
    """

    def __init__(self, maxlen: int = _MAXLEN):
        self._entries: "deque[str]" = deque(maxlen=maxlen)
        self._listeners: list = []
        self._lock = threading.Lock()

    def emit(self, line: str) -> None:
        with self._lock:
            self._entries.append(line)
            listeners = list(self._listeners)
        for q in listeners:
            try:
                q.put_nowait(line)
            except Exception:
                pass

    def snapshot(self) -> list:
        with self._lock:
            return list(self._entries)

    def add_listener(self, q) -> None:
        with self._lock:
            self._listeners.append(q)

    def remove_listener(self, q) -> None:
        with self._lock:
            if q in self._listeners:
                self._listeners.remove(q)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


# Single shared bus for the whole GUI process.
LOG_BUS = LogBus()


class _BusHandler(logging.Handler):
    """Routes log records into the shared LogBus as formatted lines."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            ts = time.strftime("%H:%M:%S", time.localtime(record.created))
            # record.name is like "demo.subscriber" -> show just the component.
            component = record.name.split(".", 1)[-1]
            line = f"[{ts}] {record.levelname:<7} {component}: {record.getMessage()}"
            LOG_BUS.emit(line)
        except Exception:
            pass


def get_logger(component: str) -> logging.Logger:
    """Return the logger for a component (e.g. 'subscriber', 'publisher')."""
    return logging.getLogger(f"demo.{component}")


def setup_logging(level: int = logging.INFO) -> None:
    """Idempotently configure the 'demo' logger tree (console + bus)."""
    root = logging.getLogger("demo")
    if getattr(root, "_demo_configured", False):
        return
    root.setLevel(level)
    root.propagate = False

    bus_handler = _BusHandler()
    bus_handler.setLevel(level)
    root.addHandler(bus_handler)

    console = logging.StreamHandler()
    console.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s",
                          "%H:%M:%S")
    )
    root.addHandler(console)

    root._demo_configured = True  # type: ignore[attr-defined]
