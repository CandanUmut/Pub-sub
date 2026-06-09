"""Subscriber panel: Subscribe / Unsubscribe plus an appending events box.

The core plumbing: a background SubscriberStream enqueues events onto a
thread-safe queue; an after()-driven drain loop (main thread only) moves them
into the Text widget. This keeps the Tk main thread responsive.
"""

import queue
import time
import tkinter as tk
from tkinter import ttk

from . import api_client

ORANGE = "#E07B39"
GREEN = "#4CAF50"


class SubscriberPanel(ttk.LabelFrame):
    def __init__(self, master):
        super().__init__(master, text="Subscriber", padding=10)

        self._queue: "queue.Queue[str]" = queue.Queue()
        self._stream = api_client.SubscriberStream(self._enqueue)
        self._draining = False
        self._after_id = None

        self.status_var = tk.StringVar(value="Unsubscribed")  # default (R2.2)
        tk.Label(self, textvariable=self.status_var,
                 font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        self.subscribe_btn = tk.Button(
            self, text="Subscribe", bg=ORANGE, fg="white",
            activebackground=ORANGE, command=self._subscribe, width=12)
        self.subscribe_btn.grid(row=1, column=0, padx=4, pady=4)

        self.unsubscribe_btn = tk.Button(
            self, text="Unsubscribe", bg=ORANGE, fg="white",
            activebackground=ORANGE, command=self._unsubscribe, width=12,
            state="disabled")
        self.unsubscribe_btn.grid(row=1, column=1, padx=4, pady=4)

        box_frame = tk.Frame(self, highlightbackground=GREEN,
                             highlightthickness=2)
        box_frame.grid(row=2, column=0, columnspan=2, pady=(8, 0), sticky="nsew")
        self.text = tk.Text(box_frame, height=10, width=36, state="disabled",
                            wrap="word")
        self.text.pack(fill="both", expand=True)

    # -- background callback (runs off the main thread) --
    def _enqueue(self, event_text: str):
        self._queue.put(event_text)

    # -- subscription control --
    def _subscribe(self):
        self._stream.start()
        self.status_var.set("Subscribed")
        self.subscribe_btn.config(state="disabled")
        self.unsubscribe_btn.config(state="normal")
        if not self._draining:
            self._draining = True
            self._drain_queue()

    def _unsubscribe(self):
        self._stream.stop()
        self._draining = False
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        self.status_var.set("Unsubscribed")
        self.subscribe_btn.config(state="normal")
        self.unsubscribe_btn.config(state="disabled")

    # -- drain loop: the only writer to the text box, on the main thread --
    def _drain_queue(self):
        try:
            while True:
                event_text = self._queue.get_nowait()
                self._append(event_text)
        except queue.Empty:
            pass
        if self._draining:
            self._after_id = self.after(100, self._drain_queue)

    def _append(self, event_text: str):
        stamp = time.strftime("%H:%M:%S")
        self.text.config(state="normal")
        self.text.insert("end", f"> [{stamp}] {event_text}\n")
        self.text.see("end")
        self.text.config(state="disabled")

    def shutdown(self):
        self._stream.stop()
