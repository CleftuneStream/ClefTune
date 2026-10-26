"""Web engine: the UI's <audio> element plays the relay URL; commands go out over SSE."""

from __future__ import annotations

import time

from ..events import EventBus
from .base import Engine


class WebEngine(Engine):
    name = "web"

    def __init__(self, on_event, bus: EventBus):
        super().__init__(on_event)
        self.bus = bus
        self.url: str | None = None
        self.volume = 80

    def _send(self, cmd: str, **data) -> None:
        self.bus.emit("engine", {"cmd": cmd, **data})

    def load(self, url: str, start: float = 0.0, paused: bool = False) -> None:
        self.url, self.pos, self.duration, self.paused = url, start, 0.0, paused
        # sticky so a UI that (re)connects later picks up the current source; ts lets it tell replays apart
        self.bus.emit("engine", {"cmd": "load", "src": url, "start": start, "paused": paused,
                                 "volume": self.volume, "ts": time.time()}, sticky=True)

    def play(self) -> None:
        self.paused = False
        self._send("play")

    def pause(self) -> None:
        self.paused = True
        self._send("pause")

    def stop(self) -> None:
        self.url, self.pos, self.duration, self.paused = None, 0.0, 0.0, True
        self.bus.emit("engine", {"cmd": "stop"}, sticky=True)

    def seek(self, seconds: float) -> None:
        self.pos = max(0.0, seconds)
        self._send("seek", pos=self.pos)

    def set_loop(self, enabled: bool) -> None:
        self.bus.emit("engine", {"cmd": "loop", "enabled": enabled})

    def set_volume(self, volume: int) -> None:
        self.volume = max(0, min(100, volume))
        self._send("volume", volume=self.volume)

    def report(self, event: str, pos: float = 0.0, duration: float = 0.0, paused: bool = True,
               message: str = "", src: str = "") -> None:
        """Called by the UI. Reports for an old source (after a track change) are ignored."""
        if src != self.url:
            return
        if event == "position":
            self.pos, self.duration, self.paused = pos, duration or self.duration, paused
            self.on_event("position", pos=self.pos, duration=self.duration, paused=self.paused)
        elif event == "ended":
            self.on_event("ended")
        elif event == "error":
            self.on_event("error", message=message or "The audio could not be played.")
