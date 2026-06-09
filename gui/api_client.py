"""HTTP helpers and the SSE subscriber stream consumer.

All network I/O lives here. The SubscriberStream runs on a background daemon
thread and never touches Tkinter widgets directly -- it only calls back with
event text, which the panel enqueues onto a thread-safe queue.
"""

import os
import threading
from typing import Callable, Optional

import requests

BROKER_URL = os.environ.get("BROKER_URL", "http://127.0.0.1:8000")


def get_status() -> str:
    """Polling read of current connection state."""
    resp = requests.get(f"{BROKER_URL}/status", timeout=5)
    resp.raise_for_status()
    return resp.json()["state"]


def publish_connect() -> str:
    resp = requests.post(f"{BROKER_URL}/connect", timeout=5)
    resp.raise_for_status()
    return resp.json()["state"]


def publish_disconnect() -> str:
    resp = requests.post(f"{BROKER_URL}/disconnect", timeout=5)
    resp.raise_for_status()
    return resp.json()["state"]


class SubscriberStream:
    """Consumes the SSE /events stream on a daemon thread.

    Subscribe = start() opens the long-lived stream. Unsubscribe = stop()
    closes it. on_event is invoked (off the main thread) for every event.
    """

    def __init__(self, on_event: Callable[[str], None]):
        self._on_event = on_event
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._resp: Optional[requests.Response] = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            self._resp = requests.get(
                f"{BROKER_URL}/events", stream=True, timeout=(5, None)
            )
            for raw in self._resp.iter_lines(decode_unicode=True):
                if self._stop.is_set():
                    break
                if not raw:
                    continue
                if raw.startswith("data:"):
                    text = raw[len("data:"):].strip()
                    if text:
                        self._on_event(text)
        except Exception:
            # Stream closed (typically by stop()) or network error; thread ends.
            pass

    def stop(self) -> None:
        """Safe to call when already stopped. Closes the stream and joins."""
        self._stop.set()
        if self._resp is not None:
            try:
                self._resp.close()  # unblocks iter_lines
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None
        self._resp = None
