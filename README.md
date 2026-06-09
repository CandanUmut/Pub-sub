# Pub/Sub + Polling Demo

A small desktop demo of two distinct communication mechanisms against a single
FastAPI **broker**:

- **Push / event-driven (pub/sub)** — a Subscriber receives `Connected` /
  `Disconnected` events over a long-lived **Server-Sent Events** stream, but
  **only while subscribed**.
- **Pull / on-demand polling** — a Polling panel reads the broker's current
  connection state with a plain `GET /status`, **only when a button is
  pressed**.

The broker (FastAPI) is the single source of truth for the connection state and
owns the set of active subscribers. The three GUI panels (Tkinter) never share
in-memory state — every action goes over HTTP/SSE to the broker, which is what
makes this real pub/sub.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

> The GUI needs Tkinter (standard library). On some Linux distros install it
> separately, e.g. `apt-get install python3-tk`.

## Run

**One command (for the demo):**

```bash
python run.py
```

This starts the backend, waits until `/status` responds, then launches the GUI
and terminates the server on exit.

**Two terminals (handy for testing):**

```bash
# Terminal 1 — broker
uvicorn backend.server:app --port 8000

# Terminal 2 — GUI
python gui/app.py
```

The backend base URL defaults to `http://127.0.0.1:8000`, overridable via the
`BROKER_URL` environment variable.

## Test

```bash
pytest -v
```

The tests spin up a real uvicorn server on a free port and exercise the actual
SSE plumbing (subscribe / emit / no-replay / unsubscribe-cleanup).

## Architecture

```
┌─────────────────────────────────────────────┐
│              FastAPI broker                  │
│   connection_state  +  subscribers (queues)  │
│                                              │
│  GET  /status      → poll current state      │
│  POST /connect     → state=CONNECTED, emit    │
│  POST /disconnect  → state=DISCONNECTED, emit │
│  GET  /events      → SSE stream (subscribe)   │
└─────────────────────────────────────────────┘
        ▲ HTTP            ▲ HTTP          ▲ SSE
        │                 │               │
   ┌────┴─────┐    ┌──────┴────┐   ┌──────┴──────┐
   │ Polling  │    │ Publisher │   │ Subscriber  │
   │ (pull)   │    │ (POST)    │   │ (push/SSE)  │
   └──────────┘    └───────────┘   └─────────────┘
```

- Network I/O never blocks the Tk main thread. The Subscriber's SSE stream runs
  on a background daemon thread and hands events to a thread-safe
  `queue.Queue`, which an `after(100, ...)` drain loop empties on the main
  thread.
- No background or periodic polling exists anywhere. The Polling panel's only
  network call happens in the `Check Status` button handler.
- Unsubscribe closes the client stream **and** the server drops that
  subscriber's queue (verified by `test_unsubscribe_stops_events`), so no
  further events reach it.
- **Unsubscribe never freezes the UI.** Closing the SSE socket and joining the
  reader thread happen on a short-lived teardown thread, so the click returns
  in ~1 ms instead of blocking the Tk main thread for several seconds.

### Activity log

The bottom-right **Activity Log** panel has a **Show Logs** button that opens a
live log window. Everything the panels do is logged through a central log bus
(`gui/logbus.py`): subscribe/unsubscribe clicks, every HTTP request and its
result, each SSE event received, stream open/close, and any errors (e.g. the
backend being unreachable). The window shows the full history on open and then
streams new lines, with errors in red and warnings in orange. Logs also go to
the console. This makes the push-vs-pull behaviour easy to narrate: you can
watch a Connect produce an `Event received` line while Subscribed, and produce
nothing on the subscriber while Unsubscribed.

### Requirement traceability

| Req | What | Where | Proven by |
|-----|------|-------|-----------|
| R1.1 | Connect/Disconnect buttons | `gui/publisher_panel.py` | checklist 6 |
| R1.2 | Persistent ConnectionState | `backend/server.py` | `test_status_default_disconnected`, `test_connect_sets_connected`, `test_disconnect_sets_disconnected` |
| R1.3 | Unambiguous state indicator | `publisher_panel._render` | checklist 2/6/7 |
| R2.1 | Subscribe/Unsubscribe + box | `gui/subscriber_panel.py` | checklist 1/5 |
| R2.2 | Default Unsubscribed | `subscriber_panel.__init__` | checklist 1 |
| R3.1 | Unsubscribed → no events | `_emit` only targets open queues | `test_unsubscribe_stops_events` |
| R3.2 | Subscribed + Connect → "Connected" | `POST /connect` emits | `test_subscriber_receives_connected` |
| R3.3 | Subscribed + Disconnect → "Disconnected" | `POST /disconnect` emits | `test_subscriber_receives_disconnected` |
| R3.4 | Append with timestamp | `subscriber_panel._append` | checklist 6 |
| emit-on-press | Every press emits | `_emit` unconditional | `test_emit_on_press_twice` |
| no-replay | Late subscriber misses past events | fresh empty queue on `/events` | `test_no_replay_for_late_subscriber` |
| R4.1–4.3 | On-demand status read | `gui/polling_panel.py` | checklist 4/10 |
| R4.4 | No background polling | no timers in polling panel | `test_polling_does_not_emit`, checklist 11 |

## The Step-12 differentiator

The key demo moment: **Unsubscribe**, then press **Connect** — nothing appears
in the Subscriber box (push is gated by subscription). Now press
**Check Status** — the Polling panel reports `Connected` (pull is always
available on demand). Same backend state change, two visibly different
mechanisms: one silent because you're not subscribed, the other answering
because you asked.
