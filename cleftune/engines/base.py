from __future__ import annotations


class Engine:
    """Plays one URL at a time and reports back through on_event(kind, **data).

    Event kinds: "position" (pos, duration, paused), "ended", "error" (message).
    """

    name = "base"

    def __init__(self, on_event):
        self.on_event = on_event
        self.pos = 0.0
        self.duration = 0.0
        self.paused = True

    def load(self, url: str, start: float = 0.0, paused: bool = False) -> None:
        raise NotImplementedError

    def play(self) -> None:
        raise NotImplementedError

    def pause(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def seek(self, seconds: float) -> None:
        raise NotImplementedError

    def set_volume(self, volume: int) -> None:
        raise NotImplementedError

    def set_normalize(self, enabled: bool) -> None:
        pass

    def set_loop(self, enabled: bool) -> None:
        """Repeat-one inside the engine: no reload, no gap. Engines without it just send "ended"."""
        pass

    @property
    def supports_loop(self) -> bool:
        return type(self).set_loop is not Engine.set_loop

    def shutdown(self) -> None:
        pass
