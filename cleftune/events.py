"""Fan-out of backend events to connected UI clients (Server-Sent Events)."""

from __future__ import annotations

import json
import queue
import threading


class EventBus:
    def __init__(self):
        self._subscribers: list[queue.Queue] = []
        self._lock = threading.Lock()
        self._last: dict[str, str] = {}     # replayed to new subscribers
        self._listeners: list = []          # in-process callbacks: fn(kind, data)

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=500)
        with self._lock:
            self._subscribers.append(q)
            for kind, payload in self._last.items():
                q.put_nowait((kind, payload))
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    @property
    def has_clients(self) -> bool:
        with self._lock:
            return bool(self._subscribers)

    def listen(self, callback) -> None:
        self._listeners.append(callback)

    def emit(self, kind: str, data, sticky: bool = False) -> None:
        payload = json.dumps(data, separators=(",", ":"))
        with self._lock:
            if sticky:
                self._last[kind] = payload
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait((kind, payload))
            except queue.Full:
                pass  # slow client: drop rather than block playback
        for callback in self._listeners:
            try:
                callback(kind, data)
            except Exception:
                pass
