"""HTTP helpers and the SSE subscriber stream consumer.

All network I/O lives here. The SubscriberStream runs on a background daemon
thread and never touches Tkinter widgets directly -- it only calls back with
event text, which the panel enqueues onto a thread-safe queue. Every network
action is logged so the activity-log window can explain what happened.
"""

import os
import threading
from typing import Callable, Optional

import requests

from .logbus import get_logger

BROKER_URL = os.environ.get("BROKER_URL", "http://127.0.0.1:8000")

_net_log = get_logger("network")


def get_status() -> str:
    """Polling read of current connection state."""
    _net_log.info("GET /status (polling read)")
    resp = requests.get(f"{BROKER_URL}/status", timeout=5)
    resp.raise_for_status()
    state = resp.json()["state"]
    _net_log.info("GET /status -> %s", state)
    return state


def publish_connect() -> str:
    _net_log.info("POST /connect")
    resp = requests.post(f"{BROKER_URL}/connect", timeout=5)
    resp.raise_for_status()
    state = resp.json()["state"]
    _net_log.info("POST /connect -> %s", state)
    return state


def publish_disconnect() -> str:
    _net_log.info("POST /disconnect")
    resp = requests.post(f"{BROKER_URL}/disconnect", timeout=5)
    resp.raise_for_status()
    state = resp.json()["state"]
    _net_log.info("POST /disconnect -> %s", state)
    return state


class SubscriberStream:
    """Consumes the SSE /events stream on a daemon thread.

    Subscribe = start() opens the long-lived stream. Unsubscribe = stop()
    closes it. on_event is invoked (off the main thread) for every event.

    stop() never blocks the caller: it signals the thread, then closes the
    socket and joins the old thread on a short-lived teardown thread. This is
    what keeps the Tk main thread from freezing on Unsubscribe.
    """

    def __init__(self, on_event: Callable[[str], None]):
        self._on_event = on_event
        self._log = get_logger("stream")
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._resp: Optional[requests.Response] = None
        self._running = False

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def start(self) -> bool:
        """Open the stream. Returns False if already running."""
        with self._lock:
            if self._running:
                self._log.debug("start() ignored: stream already running")
                return False
            self._running = True
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        self._log.info("Subscribed: opening SSE stream to %s/events", BROKER_URL)
        return True

    def _run(self) -> None:
        try:
            resp = requests.get(f"{BROKER_URL}/events", stream=True,
                                timeout=(5, None))
            with self._lock:
                self._resp = resp
            self._log.info("SSE stream open; waiting for events")
            for raw in resp.iter_lines(decode_unicode=True):
                if self._stop.is_set():
                    break
                if not raw:
                    continue
                if raw.startswith("data:"):
                    text = raw[len("data:"):].strip()
                    if text:
                        self._log.info("Event received: %s", text)
                        self._on_event(text)
        except Exception as exc:
            if not self._stop.is_set():
                self._log.error("SSE stream error: %s", exc)
        finally:
            with self._lock:
                self._running = False
            self._log.info("SSE stream closed")

    def stop(self) -> None:
        """Signal stop and tear down off the caller's thread (non-blocking)."""
        with self._lock:
            if not self._running and self._thread is None:
                return
            self._stop.set()
            resp, thread = self._resp, self._thread
            self._resp = None
            self._thread = None
            self._running = False

        self._log.info("Unsubscribed: closing SSE stream")

        def _teardown():
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass
                try:
                    # Force-close the underlying socket to unblock iter_lines.
                    resp.raw.close()  # type: ignore[union-attr]
                except Exception:
                    pass
            if thread is not None:
                thread.join(timeout=5)

        threading.Thread(target=_teardown, daemon=True).start()
