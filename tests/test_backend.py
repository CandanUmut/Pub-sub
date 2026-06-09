"""Requirement-traceability tests against a real live uvicorn server.

These exercise the real SSE plumbing (not a TestClient mock), so subscribe /
unsubscribe / emit / no-replay behavior is proven end to end.
"""

import socket
import threading
import time

import pytest
import requests
import uvicorn

from backend.server import app


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def live_server():
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            requests.get(f"{base}/status", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("live_server did not start")

    yield base

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(autouse=True)
def reset_state(live_server):
    """Reset to a known state before each test."""
    requests.post(f"{live_server}/disconnect", timeout=5)


class SSECollector:
    """Opens an SSE stream on a thread and collects `data:` events."""

    def __init__(self, base):
        self.base = base
        self.events = []
        self._resp = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._ready = threading.Event()

    def _run(self):
        self._resp = requests.get(f"{self.base}/events", stream=True,
                                  timeout=(5, None))
        self._ready.set()
        try:
            for raw in self._resp.iter_lines(decode_unicode=True):
                if raw and raw.startswith("data:"):
                    self.events.append(raw[len("data:"):].strip())
        except Exception:
            pass

    def start(self):
        self._thread.start()
        self._ready.wait(timeout=5)
        # Give the server a moment to register the subscriber queue.
        time.sleep(0.3)

    def wait_for(self, count, timeout=3.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if len(self.events) >= count:
                return True
            time.sleep(0.05)
        return len(self.events) >= count

    def close(self):
        if self._resp is not None:
            self._resp.close()
        self._thread.join(timeout=2)


def test_status_default_disconnected(live_server):
    # R1.2 -- after reset, status reports DISCONNECTED.
    r = requests.get(f"{live_server}/status", timeout=5)
    assert r.json()["state"] == "DISCONNECTED"


def test_connect_sets_connected(live_server):
    # R1.2
    requests.post(f"{live_server}/connect", timeout=5)
    assert requests.get(f"{live_server}/status", timeout=5).json()["state"] == "CONNECTED"


def test_disconnect_sets_disconnected(live_server):
    # R1.2
    requests.post(f"{live_server}/connect", timeout=5)
    requests.post(f"{live_server}/disconnect", timeout=5)
    assert requests.get(f"{live_server}/status", timeout=5).json()["state"] == "DISCONNECTED"


def test_subscriber_receives_connected(live_server):
    # R3.2
    sub = SSECollector(live_server)
    sub.start()
    requests.post(f"{live_server}/connect", timeout=5)
    assert sub.wait_for(1)
    assert "Connected" in sub.events
    sub.close()


def test_subscriber_receives_disconnected(live_server):
    # R3.3
    requests.post(f"{live_server}/connect", timeout=5)
    sub = SSECollector(live_server)
    sub.start()
    requests.post(f"{live_server}/disconnect", timeout=5)
    assert sub.wait_for(1)
    assert "Disconnected" in sub.events
    sub.close()


def test_emit_on_press_twice(live_server):
    # emit-on-press: two connect presses -> two Connected events
    sub = SSECollector(live_server)
    sub.start()
    requests.post(f"{live_server}/connect", timeout=5)
    requests.post(f"{live_server}/connect", timeout=5)
    assert sub.wait_for(2)
    assert sub.events.count("Connected") == 2
    sub.close()


def test_no_replay_for_late_subscriber(live_server):
    # no replay: event before subscribing is not delivered
    requests.post(f"{live_server}/connect", timeout=5)
    sub = SSECollector(live_server)
    sub.start()
    time.sleep(0.5)
    assert sub.events == []
    sub.close()


def test_unsubscribe_stops_events(live_server):
    # R3.1 / cleanup: closed stream receives nothing and queue is dropped
    sub = SSECollector(live_server)
    sub.start()
    sub.close()
    # Allow the server's finally block to drop the queue.
    time.sleep(0.5)
    requests.post(f"{live_server}/connect", timeout=5)
    time.sleep(0.5)
    assert sub.events == []
    # Server reports zero subscribers.
    assert requests.get(f"{live_server}/", timeout=5).json()["subscribers"] == 0


def test_polling_does_not_emit(live_server):
    # R4 vs R3 separation: polling never produces subscriber events
    sub = SSECollector(live_server)
    sub.start()
    for _ in range(5):
        requests.get(f"{live_server}/status", timeout=5)
    time.sleep(0.5)
    assert sub.events == []
    sub.close()
