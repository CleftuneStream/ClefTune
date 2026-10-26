"""libmpv engine: native decoding, gapless-friendly, low memory."""

from __future__ import annotations

import threading
import time

from . import prepare_libmpv_search_path
from .base import Engine

LOUDNORM = "lavfi=[loudnorm=I=-14:TP=-1.5:LRA=11]"


class MpvEngine(Engine):
    name = "mpv"

    def __init__(self, on_event):
        super().__init__(on_event)
        prepare_libmpv_search_path()
        import mpv

        self._mpv_mod = mpv
        self.m = mpv.MPV(video=False, ytdl=False, terminal=False, input_default_bindings=False,
                         cache=True, demuxer_max_bytes="64MiB", audio_client_name="ClefTune", idle=True)
        self._last_emit = 0.0

        @self.m.property_observer("time-pos")
        def _time(_name, value):
            if value is None:
                return
            self.pos = float(value)
            now = time.monotonic()
            if now - self._last_emit >= 0.25:
                self._last_emit = now
                self._report()

        @self.m.property_observer("duration")
        def _duration(_name, value):
            if value:
                self.duration = float(value)
                self._report()

        @self.m.property_observer("pause")
        def _pause(_name, value):
            self.paused = bool(value)
            self._report()

        @self.m.event_callback("end-file")
        def _end(event):
            data = event.data
            reason = getattr(data, "reason", None)
            if reason == mpv.MpvEventEndFile.EOF:
                threading.Thread(target=self.on_event, args=("ended",), daemon=True).start()
            elif reason == mpv.MpvEventEndFile.ERROR:
                code = getattr(data, "error", 0)
                try:
                    text = mpv.ErrorCode.human_readable(code)
                except Exception:
                    text = f"error {code}"
                threading.Thread(target=self.on_event, args=("error",), kwargs={"message": f"mpv: {text}"},
                                 daemon=True).start()

    def _report(self):
        self.on_event("position", pos=self.pos, duration=self.duration, paused=self.paused)

    def load(self, url: str, start: float = 0.0, paused: bool = False) -> None:
        self.pos, self.duration = start, 0.0
        self.m.pause = paused
        options = {"start": f"{start:.2f}"} if start > 0 else {}
        self.m.loadfile(url, "replace", **options)

    def play(self) -> None:
        self.m.pause = False

    def pause(self) -> None:
        self.m.pause = True

    def stop(self) -> None:
        self.m.command("stop")
        self.pos, self.duration, self.paused = 0.0, 0.0, True

    def seek(self, seconds: float) -> None:
        try:
            self.m.seek(max(0.0, seconds), reference="absolute")
        except SystemError:
            pass  # nothing loaded yet

    def set_volume(self, volume: int) -> None:
        self.m.volume = max(0, min(100, volume))

    def set_normalize(self, enabled: bool) -> None:
        self.m.af = LOUDNORM if enabled else ""

    def set_loop(self, enabled: bool) -> None:
        self.m.loop_file = "inf" if enabled else "no"

    def shutdown(self) -> None:
        try:
            self.m.terminate()
        except Exception:
            pass
