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
else:
    from .publisher_panel import PublisherPanel
    from .subscriber_panel import SubscriberPanel
    from .polling_panel import PollingPanel


def main():
    root = tk.Tk()
    root.title("Pub/Sub + Polling Demo")

    subscriber = SubscriberPanel(root)
    subscriber.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

    publisher = PublisherPanel(root)
    publisher.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

    polling = PollingPanel(root)
    polling.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=1)
    root.rowconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)

    def on_close():
        subscriber.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
