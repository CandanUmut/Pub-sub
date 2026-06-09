"""Polling panel: Check Status reads current state on press only (R4).

There are deliberately NO timers and NO after() loops here -- the only network
call happens in the button handler.
"""

import time
import tkinter as tk
from tkinter import ttk

from . import api_client

ORANGE = "#E07B39"
GREEN = "#4CAF50"


class PollingPanel(ttk.LabelFrame):
    def __init__(self, master):
        super().__init__(master, text="Polling", padding=10)

        self.check_btn = tk.Button(
            self, text="Check Status", bg=ORANGE, fg="white",
            activebackground=ORANGE, command=self._on_check, width=14)
        self.check_btn.grid(row=0, column=0, padx=4, pady=4, sticky="w")

        box_frame = tk.Frame(self, highlightbackground=GREEN,
                             highlightthickness=2)
        box_frame.grid(row=1, column=0, pady=(8, 0), sticky="nsew")
        self.text = tk.Text(box_frame, height=10, width=36, state="disabled",
                            wrap="word")
        self.text.pack(fill="both", expand=True)

    def _on_check(self):
        """Single on-demand read. No background polling anywhere (R4.1/R4.4)."""
        try:
            state = api_client.get_status()
        except Exception as exc:
            self._append(f"ERROR: {exc}")
            return
        self._append("Connected" if state == "CONNECTED" else "Disconnected")

    def _append(self, line: str):
        stamp = time.strftime("%H:%M:%S")
        self.text.config(state="normal")
        self.text.insert("end", f"> [{stamp}] {line}\n")
        self.text.see("end")
        self.text.config(state="disabled")
