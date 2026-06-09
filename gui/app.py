"""Main window: lays out the three independent panels on a grid.

Run directly with `python gui/app.py` (after starting the backend), or via
`python run.py` which starts the backend for you.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk

# Allow `python gui/app.py` by making the package importable.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from gui.publisher_panel import PublisherPanel
    from gui.subscriber_panel import SubscriberPanel
    from gui.polling_panel import PollingPanel
    from gui.log_window import LogWindow
    from gui.logbus import setup_logging, get_logger
else:
    from .publisher_panel import PublisherPanel
    from .subscriber_panel import SubscriberPanel
    from .polling_panel import PollingPanel
    from .log_window import LogWindow
    from .logbus import setup_logging, get_logger

ORANGE = "#E07B39"


class ControlsPanel(ttk.LabelFrame):
    """Bottom-right helper panel: open the activity log window."""

    def __init__(self, master):
        super().__init__(master, text="Activity Log", padding=10)
        self._log_window = None

        tk.Label(self, text="Open the log to see what each panel does,\n"
                            "the events it receives, and any errors.",
                 justify="left").grid(row=0, column=0, sticky="w", pady=(0, 8))
        tk.Button(self, text="Show Logs", bg=ORANGE, fg="white",
                 activebackground=ORANGE, width=14,
                 command=self._show_logs).grid(row=1, column=0, sticky="w")

    def _show_logs(self):
        if self._log_window is not None and self._log_window.winfo_exists():
            self._log_window.lift()
            self._log_window.focus_force()
            return
        self._log_window = LogWindow(self)


def main():
    setup_logging()
    log = get_logger("app")

    root = tk.Tk()
    root.title("Pub/Sub + Polling Demo")
    log.info("Application started.")

    subscriber = SubscriberPanel(root)
    subscriber.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

    publisher = PublisherPanel(root)
    publisher.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

    polling = PollingPanel(root)
    polling.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

    controls = ControlsPanel(root)
    controls.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=1)
    root.rowconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)

    def on_close():
        log.info("Application closing; shutting down subscriber stream.")
        subscriber.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
