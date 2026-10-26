"""Native engine: decodes with FFmpeg (PyAV) inside the app process and plays through miniaudio.

Audio is independent of any window or browser tab, so closing the UI never stops the music.
Both libraries ship as self-contained wheels on Windows, macOS and Linux.
"""

from __future__ import annotations

import collections
import os
import threading
import time
from array import array

import av
import miniaudio

from .base import Engine

RATE = 48000
CHANNELS = 2
FRAME_BYTES = 2 * CHANNELS            # signed 16-bit stereo
BUFFER_SECONDS = 1.5                  # decoded audio kept ahead of the speakers
REPORT_INTERVAL = 0.2


class NativeEngine(Engine):
    name = "native"

    def __init__(self, on_event):
        super().__init__(on_event)
        self._cond = threading.Condition()
        self._chunks: collections.deque[bytes] = collections.deque()
        self._chunk_pos = 0                       # bytes already consumed from _chunks[0]
        self._buffered = 0                        # bytes waiting in _chunks
        self._pushed = 0                          # frames handed to the buffer (this session)
        self._played = 0                          # frames sent to the device (this session)
        self._marks: collections.deque = collections.deque()  # (frame, seconds): position resets (loops)
        self._seg_frame, self._seg_base = 0, 0.0
        self._session = 0
        self._url: str | None = None
        self._eof = True
        self._ended_sent = True
        self._loop = False
        self._gain = 0.64
        self.paused = True
        backends = [miniaudio.Backend.NULL] if os.environ.get("CLEFTUNE_AUDIO_BACKEND") == "null" else None
        self.device = miniaudio.PlaybackDevice(output_format=miniaudio.SampleFormat.SIGNED16, nchannels=CHANNELS,
                                               sample_rate=RATE, buffersize_msec=80, backends=backends,
                                               app_name="ClefTune")
        gen = self._feed()
        next(gen)
        self.device.start(gen)
        self._alive = True
        threading.Thread(target=self._ticker, name="native-ticker", daemon=True).start()

    # -- audio callback (miniaudio thread): must never block for long -----
    def _feed(self):
        required = yield b""
        while True:
            want = required * FRAME_BYTES
            out = bytearray()
            with self._cond:
                if not self.paused:
                    while len(out) < want and self._chunks:
                        head = self._chunks[0]
                        take = head[self._chunk_pos:self._chunk_pos + want - len(out)]
                        out += take
                        self._chunk_pos += len(take)
                        if self._chunk_pos >= len(head):
                            self._chunks.popleft()
                            self._chunk_pos = 0
                    self._buffered -= len(out)
                    self._played += len(out) // FRAME_BYTES
                    while self._marks and self._played >= self._marks[0][0]:
                        self._seg_frame, self._seg_base = self._marks.popleft()
                    if out:
                        self._cond.notify_all()
            gain = self._gain
            if out and gain < 0.999:
                samples = memoryview(out).cast("h")
                out = array("h", [int(s * gain) for s in samples]).tobytes()
            if len(out) < want:
                out = bytes(out) + bytes(want - len(out))
            required = yield bytes(out)

    # -- decoding (one thread per load/seek "session") --------------------
    def _push(self, data: bytes, session: int) -> bool:
        with self._cond:
            while self._buffered > BUFFER_SECONDS * RATE * FRAME_BYTES and session == self._session:
                self._cond.wait(0.25)
            if session != self._session:
                return False
            self._chunks.append(data)
            self._buffered += len(data)
            self._pushed += len(data) // FRAME_BYTES
            return True

    def _decode(self, url: str, start: float, session: int) -> None:
        position = start
        try:
            while True:
                with av.open(url, timeout=(15, 30)) as container:
                    stream = container.streams.audio[0]
                    if container.duration:
                        self.duration = container.duration / av.time_base
                    elif stream.duration and stream.time_base:
                        self.duration = float(stream.duration * stream.time_base)
                    resampler = av.AudioResampler(format="s16", layout="stereo", rate=RATE)
                    if position > 0.5:
                        container.seek(int(position / stream.time_base), stream=stream, backward=True)
                    skip_to = position
                    for packet in container.demux(stream):
                        for frame in packet.decode():
                            t = float(frame.time) if frame.time is not None else None
                            for out in resampler.resample(frame):
                                data = bytes(out.planes[0])[:out.samples * FRAME_BYTES]
                                if skip_to and t is not None:      # exact seek: drop audio before the target
                                    drop = int((skip_to - t) * RATE) * FRAME_BYTES
                                    if drop >= len(data):
                                        t += out.samples / RATE
                                        continue
                                    data = data[max(0, drop):]
                                    skip_to = 0.0
                                if not self._push(data, session):
                                    return
                    for out in resampler.resample(None):
                        if not self._push(bytes(out.planes[0])[:out.samples * FRAME_BYTES], session):
                            return
                with self._cond:
                    if session != self._session:
                        return
                    if not self._loop:
                        self._eof = True
                        return
                    # repeat-one: keep decoding from the start, gapless; position resets when it's heard
                    self._marks.append((self._pushed, 0.0))
                position = 0.0
        except Exception as exc:  # network/decoder errors
            with self._cond:
                current = session == self._session
            if current:
                self.on_event("error", message=f"Playback error: {exc}")

    def _start_session(self, url: str, start: float) -> None:
        with self._cond:
            self._session += 1
            session = self._session
            self._chunks.clear()
            self._chunk_pos = self._buffered = self._pushed = self._played = 0
            self._marks.clear()
            self._seg_frame, self._seg_base = 0, max(0.0, start)
            self._eof = False
            self._ended_sent = False
            self._cond.notify_all()
        threading.Thread(target=self._decode, args=(url, start, session), name="native-decode", daemon=True).start()

    # -- position reporting and end-of-track detection --------------------
    def _position(self) -> float:
        return self._seg_base + (self._played - self._seg_frame) / RATE

    def _ticker(self) -> None:
        while self._alive:
            time.sleep(REPORT_INTERVAL)
            with self._cond:
                if self._url is None:
                    continue
                self.pos = self._position()
                finished = self._eof and self._buffered == 0 and not self._ended_sent
                if finished:
                    self._ended_sent = True
                paused = self.paused
            if finished:
                self.on_event("ended")
            elif not paused:
                self.on_event("position", pos=self.pos, duration=self.duration, paused=False)

    # -- Engine API -------------------------------------------------------
    def load(self, url: str, start: float = 0.0, paused: bool = False) -> None:
        self._url = url
        self.pos, self.duration = start, 0.0
        self.paused = paused
        self._start_session(url, start)
        self.on_event("position", pos=start, duration=0.0, paused=paused)

    def play(self) -> None:
        self.paused = False
        self.on_event("position", pos=self.pos, duration=self.duration, paused=False)

    def pause(self) -> None:
        self.paused = True
        with self._cond:
            self.pos = self._position()
        self.on_event("position", pos=self.pos, duration=self.duration, paused=True)

    def stop(self) -> None:
        with self._cond:
            self._session += 1
            self._chunks.clear()
            self._buffered = 0
            self._cond.notify_all()
        self._url = None
        self.pos, self.duration, self.paused = 0.0, 0.0, True

    def seek(self, seconds: float) -> None:
        if self._url is None:
            return
        self.pos = max(0.0, seconds)
        self._start_session(self._url, self.pos)
        self.on_event("position", pos=self.pos, duration=self.duration, paused=self.paused)

    def set_volume(self, volume: int) -> None:
        self._gain = (max(0, min(100, volume)) / 100) ** 2      # perceptual curve

    def set_loop(self, enabled: bool) -> None:
        self._loop = enabled

    def shutdown(self) -> None:
        self._alive = False
        self.stop()
        try:
            self.device.close()
        except Exception:
            pass
