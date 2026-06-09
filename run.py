"""Convenience launcher: start the backend, wait for it, then launch the GUI.

The uvicorn server runs as a subprocess and is terminated when the GUI exits.
"""

import os
import subprocess
import sys
import time

import requests

BROKER_URL = os.environ.get("BROKER_URL", "http://127.0.0.1:8000")


def wait_for_server(timeout=15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            requests.get(f"{BROKER_URL}/status", timeout=1)
            return True
        except Exception:
            time.sleep(0.25)
    return False


def main():
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.server:app",
         "--host", "127.0.0.1", "--port", "8000"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    try:
        if not wait_for_server():
            print("Backend failed to start in time.", file=sys.stderr)
            server.terminate()
            return 1

        from gui.app import main as gui_main
        gui_main()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
