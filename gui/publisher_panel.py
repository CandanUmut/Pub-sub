"""Publisher panel: Connect / Disconnect plus an unambiguous state indicator."""

import tkinter as tk
from tkinter import ttk

from . import api_client
from .logbus import get_logger

ORANGE = "#E07B39"
GREEN = "#4CAF50"
RED = "#C0392B"
GREY = "#7F8C8D"


class PublisherPanel(ttk.LabelFrame):
    def __init__(self, master):
        super().__init__(master, text="Publisher", padding=10)
        self._log = get_logger("publisher")

        self.state_var = tk.StringVar(value="STATE: DISCONNECTED")
        self.indicator = tk.Label(
            self,
            textvariable=self.state_var,
            font=("TkDefaultFont", 12, "bold"),
            fg="white",
            bg=GREY,
            width=24,
            pady=8,
        )
        self.indicator.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky="ew")

        self.connect_btn = tk.Button(
            self, text="Connect", bg=ORANGE, fg="white",
            activebackground=ORANGE, command=self._on_connect, width=12,
        )
        self.connect_btn.grid(row=1, column=0, padx=4, pady=4)

        self.disconnect_btn = tk.Button(
            self, text="Disconnect", bg=ORANGE, fg="white",
            activebackground=ORANGE, command=self._on_disconnect, width=12,
        )
        self.disconnect_btn.grid(row=1, column=1, padx=4, pady=4)

        # One-time init read of real state (not polling).
        try:
            state = api_client.get_status()
            self._render(state)
            self._log.info("Init read of /status -> %s (one-time, not polling).",
                          state)
        except Exception as exc:
            self._render("DISCONNECTED")
            self._log.error("Init read of /status failed: %s. Is the backend "
                           "running?", exc)

    def _on_connect(self):
        self._log.info("Connect clicked -> publishing 'Connected' to broker.")
        try:
            self._render(api_client.publish_connect())
        except Exception as exc:
            self.state_var.set("ERROR (see log)")
            self._log.error("Connect failed: %s", exc)

    def _on_disconnect(self):
        self._log.info("Disconnect clicked -> publishing 'Disconnected' to broker.")
        try:
            self._render(api_client.publish_disconnect())
        except Exception as exc:
            self.state_var.set("ERROR (see log)")
            self._log.error("Disconnect failed: %s", exc)

    def _render(self, state: str):
        """Update the indicator and emphasize the active button (R1.3)."""
        if state == "CONNECTED":
            self.state_var.set("STATE: CONNECTED")
            self.indicator.config(bg=GREEN)
            self.connect_btn.config(relief="sunken")
            self.disconnect_btn.config(relief="raised")
        else:
            self.state_var.set("STATE: DISCONNECTED")
            self.indicator.config(bg=RED)
            self.disconnect_btn.config(relief="sunken")
            self.connect_btn.config(relief="raised")
