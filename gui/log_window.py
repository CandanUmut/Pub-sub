"""A Toplevel window that shows the live activity log.

Opens with the full history snapshot, then appends new lines as they arrive via
a listener queue drained on the Tk main thread. Closing the window unregisters
the listener and cancels its refresh loop.
"""

import queue
import tkinter as tk
from tkinter import ttk

from . import logbus

GREEN = "#4CAF50"
LEVEL_COLORS = {
    "ERROR": "#C0392B",
    "WARNING": "#E07B39",
    "DEBUG": "#7F8C8D",
}


class LogWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Activity Log")
        self.geometry("680x420")

        self._queue: "queue.Queue[str]" = queue.Queue()
        self._after_id = None

        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        ttk.Label(bar, text="Live activity — what each panel does, "
                            "events, and errors").pack(side="left")
        tk.Button(bar, text="Clear", command=self._clear).pack(side="right")

        box_frame = tk.Frame(self, highlightbackground=GREEN, highlightthickness=2)
        box_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text = tk.Text(box_frame, state="disabled", wrap="word",
                            font=("TkFixedFont", 9))
        scroll = ttk.Scrollbar(box_frame, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        for level, color in LEVEL_COLORS.items():
            self.text.tag_configure(level, foreground=color)

        # Render existing history, then go live.
        for line in logbus.LOG_BUS.snapshot():
            self._append(line)
        logbus.LOG_BUS.add_listener(self._queue)
        self._after_id = self.after(200, self._drain)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _drain(self):
        try:
            while True:
                self._append(self._queue.get_nowait())
        except queue.Empty:
            pass
        self._after_id = self.after(200, self._drain)

    def _append(self, line: str):
        tag = ""
        for level in LEVEL_COLORS:
            if f" {level:<7} " in line or f" {level} " in line:
                tag = level
                break
        self.text.config(state="normal")
        self.text.insert("end", line + "\n", tag)
        self.text.see("end")
        self.text.config(state="disabled")

    def _clear(self):
        logbus.LOG_BUS.clear()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")

    def _on_close(self):
        logbus.LOG_BUS.remove_listener(self._queue)
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        self.destroy()
