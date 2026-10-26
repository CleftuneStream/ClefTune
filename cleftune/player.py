"""Playback controller: queue, shuffle/repeat, autoplay radio, sleep timer, error recovery."""

from __future__ import annotations

import itertools
import json
import random
import threading
import time
from typing import Callable

from .config import Settings, data_dir
from .engines.base import Engine
from .events import EventBus
from .library import Library
from .streams import StreamResolver

REPEAT_MODES = ("off", "all", "one")


class Player:
    def __init__(self, settings: Settings, library: Library, ytm, resolver: StreamResolver, bus: EventBus):
        self.settings, self.library, self.ytm, self.resolver, self.bus = settings, library, ytm, resolver, bus
        self.engine: Engine | None = None
        self.stream_url: Callable[[str, int], str] = lambda video_id, gen: ""
        self._lock = threading.RLock()
        self._ids = itertools.count(1)
        self.queue: list[dict] = []
        self.original: list[dict] | None = None     # unshuffled order while shuffle is on
        self.index = -1
        self.title = ""
        self.version = 0
        self.shuffle = False
        self.repeat = "off"
        self.volume = int(settings.get("volume"))
        self.pos = 0.0
        self.duration = 0.0
        self.paused = True
        self.loaded = False
        self.loading = False
        self.error: str | None = None
        self.stream_label = ""
        self.gen = 0
        self._retried: set[int] = set()
        self._extending = threading.Lock()
        self.sleep_deadline: float | None = None
        self.sleep_end_of_song = False
        self._session_path = data_dir() / "session.json"
        self.track_listeners: list[Callable[[dict], None]] = []   # called when a song starts playing

    def attach(self, engine: Engine, stream_url: Callable[[str, int], str]) -> None:
        self.engine, self.stream_url = engine, stream_url
        engine.set_volume(self.volume)
        engine.set_normalize(bool(self.settings.get("normalize")))
        self._sync_loop()

    def _sync_loop(self) -> None:
        # repeat-one loops inside the engine (gapless, no reload) unless "stop after this song" is set
        if self.engine:
            self.engine.set_loop(self.repeat == "one" and not self.sleep_end_of_song)

    # -- snapshots for the UI ---------------------------------------------
    @property
    def current(self) -> dict | None:
        return self.queue[self.index] if 0 <= self.index < len(self.queue) else None

    def state(self) -> dict:
        with self._lock:
            cur = self.current
            sleep = None
            if self.sleep_end_of_song:
                sleep = "end"
            elif self.sleep_deadline:
                sleep = max(0, round(self.sleep_deadline - time.time()))
            return {
                "current": cur, "index": self.index, "playing": self.loaded and not self.paused,
                "loading": self.loading, "error": self.error, "shuffle": self.shuffle, "repeat": self.repeat,
                "volume": self.volume, "sleep": sleep, "stream": self.stream_label,
                "liked": bool(cur and self.library.is_liked(cur["videoId"])),
                "engine": self.engine.name if self.engine else None, "queueVersion": self.version, "gen": self.gen,
                "pos": self.pos, "duration": self.duration or (cur or {}).get("duration") or 0,
            }

    def queue_payload(self) -> dict:
        with self._lock:
            return {"version": self.version, "title": self.title, "items": list(self.queue), "index": self.index}

    def _emit_state(self) -> None:
        self.bus.emit("state", self.state(), sticky=True)

    def _emit_queue(self) -> None:
        with self._lock:
            self.version += 1
        self.bus.emit("queue", self.queue_payload(), sticky=True)
        self._emit_state()

    def _entry(self, track: dict) -> dict:
        return {k: v for k, v in track.items() if k not in ("qid", "plays", "playedAt", "status", "progress",
                                                             "path", "error")} | {"qid": next(self._ids)}

    # -- starting tracks --------------------------------------------------
    def _start(self, index: int, start: float = 0.0, paused: bool = False) -> None:
        with self._lock:
            if not 0 <= index < len(self.queue):
                return
            self.index = index
            self.gen += 1
            gen = self.gen
            self.loading, self.error, self.loaded = True, None, False
            self.pos, self.duration, self.paused = start, self.queue[index].get("duration") or 0, paused
            track = self.queue[index]
        self._emit_state()
        self.bus.emit("queue-index", {"index": index, "version": self.version})
        threading.Thread(target=self._load, args=(track, gen, start, paused), daemon=True).start()

    def _load(self, track: dict, gen: int, start: float, paused: bool) -> None:
        try:
            info = self.resolver.resolve(track["videoId"])
        except Exception as exc:
            self._failed(gen, str(exc) or "Could not load this song.")
            return
        with self._lock:
            if gen != self.gen:
                return
            self.stream_label = info.describe()
            self.loaded, self.loading = True, False
            if info.duration:
                self.duration = info.duration
        self.engine.load(self.stream_url(track["videoId"], gen), start=start, paused=paused)
        if not paused:
            self.library.add_history(track)
            for listener in self.track_listeners:
                try:
                    listener(track)
                except Exception:
                    pass
        self._emit_state()
        self._after_start()

    def _after_start(self) -> None:
        with self._lock:
            upcoming = self.queue[self.index + 1:self.index + 3]
            remaining = len(self.queue) - self.index - 1
        for track in upcoming:
            self.resolver.prefetch(track["videoId"])
        if remaining <= 2 and self.settings.get("autoplay") and self.repeat == "off":
            threading.Thread(target=self.extend_autoplay, daemon=True).start()

    def _failed(self, gen: int, message: str) -> None:
        with self._lock:
            if gen != self.gen:
                return
            self.loading, self.loaded, self.error = False, False, message
        self._emit_state()
        self.bus.emit("toast", {"message": message, "kind": "error"})
        if self.settings.get("skip_on_error"):
            def skip():
                time.sleep(2.5)
                with self._lock:
                    if gen != self.gen or self.index + 1 >= len(self.queue):
                        return
                self.next()
            threading.Thread(target=skip, daemon=True).start()

    # -- engine callbacks -------------------------------------------------
    def on_engine_event(self, kind: str, **data) -> None:
        if kind == "position":
            with self._lock:
                self.pos = data.get("pos", self.pos)
                self.duration = data.get("duration") or self.duration
                was_paused, self.paused = self.paused, data.get("paused", self.paused)
                sleep_due = self.sleep_deadline and time.time() >= self.sleep_deadline
            self.bus.emit("position", {"pos": self.pos, "duration": self.duration, "playing": not self.paused,
                                       "gen": self.gen}, sticky=True)
            if was_paused != self.paused:
                self._emit_state()
            if sleep_due:
                self.sleep_deadline = None
                self.pause()
                self.bus.emit("toast", {"message": "Sleep timer: playback paused"})
        elif kind == "ended":
            self._on_ended()
        elif kind == "error":
            with self._lock:
                gen, track, pos = self.gen, self.current, self.pos
                retry = gen not in self._retried
                self._retried.add(gen)
            if not track:
                return
            if retry:
                # usually an expired or rejected stream URL: fetch a fresh one and resume
                self.resolver.invalidate(track["videoId"])
                self._start(self.index, start=pos)
            else:
                self._failed(gen, data.get("message") or "Playback failed.")

    def _on_ended(self) -> None:
        with self._lock:
            end_of_song_sleep = self.sleep_end_of_song
            repeat_one = self.repeat == "one"
        if end_of_song_sleep:
            self.sleep_end_of_song = False
            self._sync_loop()
            self.stop()
            self.bus.emit("toast", {"message": "Sleep timer: playback stopped"})
        elif repeat_one:
            self._start(self.index)
        else:
            self.next(auto=True)

    # -- transport --------------------------------------------------------
    def play(self) -> None:
        with self._lock:
            needs_load = not self.loaded and self.current is not None and not self.loading
            pos = self.pos
        if needs_load:
            self._start(self.index, start=pos)
        elif self.engine:
            self.engine.play()
            with self._lock:
                self.paused = False
            self._emit_state()

    def pause(self) -> None:
        if self.engine:
            self.engine.pause()
        with self._lock:
            self.paused = True
        self._emit_state()

    def toggle(self) -> None:
        with self._lock:
            playing = self.loaded and not self.paused
        self.pause() if playing else self.play()

    def stop(self) -> None:
        if self.engine:
            self.engine.stop()
        with self._lock:
            self.paused, self.loaded, self.pos = True, False, 0.0
        self._emit_state()

    def next(self, auto: bool = False) -> None:
        with self._lock:
            has_next = self.index + 1 < len(self.queue)
            wrap = self.repeat == "all" and bool(self.queue)
            nxt = self.index + 1
        if has_next:
            self._start(nxt)
        elif wrap:
            self._start(0)
        elif self.settings.get("autoplay") and self.current:
            def extend_then_play():
                if self.extend_autoplay():
                    self._start(nxt)
                elif auto:
                    self.stop()
            threading.Thread(target=extend_then_play, daemon=True).start()
        elif auto:
            self.stop()

    def previous(self) -> None:
        with self._lock:
            restart = self.pos > 3 or self.index <= 0
        if restart:
            self.seek(0)
        else:
            self._start(self.index - 1)

    def seek(self, seconds: float) -> None:
        seconds = max(0.0, float(seconds))
        with self._lock:
            self.pos = seconds
            loaded = self.loaded
        if loaded and self.engine:
            self.engine.seek(seconds)
        self.bus.emit("position", {"pos": seconds, "duration": self.duration, "playing": not self.paused,
                                   "gen": self.gen}, sticky=True)

    def set_volume(self, volume: int) -> None:
        self.volume = max(0, min(100, int(volume)))
        if self.engine:
            self.engine.set_volume(self.volume)
        self._emit_state()

    def set_repeat(self, mode: str) -> None:
        if mode not in REPEAT_MODES:
            raise ValueError("repeat must be off, all or one")
        self.repeat = mode
        self._sync_loop()
        self._emit_state()

    def set_sleep(self, minutes: float) -> None:
        """minutes > 0: pause after that long; -1: stop at end of song; 0: cancel."""
        self.sleep_end_of_song = minutes == -1
        self.sleep_deadline = time.time() + minutes * 60 if minutes > 0 else None
        self._sync_loop()
        self._emit_state()

    def prefetch(self, video_ids: list[str]) -> None:
        """Hint that these songs may be played soon (e.g. the pointer is over them)."""
        for video_id in video_ids[:3]:
            self.resolver.prefetch(video_id)

    # -- queue building ---------------------------------------------------
    def play_tracks(self, tracks: list[dict], index: int = 0, title: str = "", shuffle: bool = False) -> None:
        if not tracks:
            return
        index = max(0, min(index, len(tracks) - 1))
        if shuffle:
            index = random.randrange(len(tracks))
        with self._lock:
            self.queue = [self._entry(t) for t in tracks]
            self.original = None
            self.title = title
            self.shuffle = False
            if shuffle:
                self._apply_shuffle(index)
                index = 0
        self.library.upsert(tracks)
        self._emit_queue()
        self._start(index)

    def play_radio(self, track: dict) -> None:
        """Play a song and fill the queue with YouTube Music's 'up next' for it."""
        self.play_tracks([track], title=f"Radio • {track.get('title', '')}")

        def fill():
            try:
                data = self.ytm.up_next(video_id=track["videoId"])
            except Exception as exc:
                self.bus.emit("toast", {"message": f"Couldn't load up next: {exc}", "kind": "error"})
                return
            self._append_unique(data["tracks"])
        threading.Thread(target=fill, daemon=True).start()

    def play_playlist_radio(self, playlist_id: str, title: str = "") -> None:
        data = self.ytm.up_next(playlist_id=playlist_id)
        self.play_tracks(data["tracks"], title=title or "Mix")

    def extend_autoplay(self) -> int:
        if not self._extending.acquire(blocking=False):
            return 0
        try:
            with self._lock:
                seed = self.queue[-1] if self.queue else None
            if not seed:
                return 0
            try:
                data = self.ytm.up_next(video_id=seed["videoId"])
            except Exception:
                return 0
            return self._append_unique(data["tracks"])
        finally:
            self._extending.release()

    def _append_unique(self, tracks: list[dict]) -> int:
        with self._lock:
            seen = {t["videoId"] for t in self.queue}
            fresh = [self._entry(t) for t in tracks if t["videoId"] not in seen]
            self.queue.extend(fresh)
            if self.original is not None:
                self.original.extend(fresh)
        if fresh:
            self.library.upsert(fresh)
            self._emit_queue()
        return len(fresh)

    def add_next(self, tracks: list[dict]) -> None:
        if not self.queue:
            return self.play_tracks(tracks)
        entries = [self._entry(t) for t in tracks]
        with self._lock:
            self.queue[self.index + 1:self.index + 1] = entries
            if self.original is not None:
                self.original.extend(entries)
        self._emit_queue()

    def add_to_queue(self, tracks: list[dict]) -> None:
        if not self.queue:
            return self.play_tracks(tracks)
        entries = [self._entry(t) for t in tracks]
        with self._lock:
            self.queue.extend(entries)
            if self.original is not None:
                self.original.extend(entries)
        self._emit_queue()

    def remove(self, index: int) -> None:
        with self._lock:
            if not 0 <= index < len(self.queue):
                return
            removed = self.queue.pop(index)
            if self.original is not None:
                self.original = [t for t in self.original if t["qid"] != removed["qid"]]
            action = None
            if index == self.index:
                if self.index < len(self.queue):
                    action = "start"        # the next song slid into the current slot
                else:
                    self.index = len(self.queue) - 1
                    action = "stop"
            elif index < self.index:
                self.index -= 1
        self._emit_queue()
        if action == "start":
            self._start(self.index)
        elif action == "stop":
            self.stop()

    def move(self, src: int, dst: int) -> None:
        with self._lock:
            n = len(self.queue)
            if not (0 <= src < n and 0 <= dst < n) or src == dst:
                return
            item = self.queue.pop(src)
            self.queue.insert(dst, item)
            if src == self.index:
                self.index = dst
            elif src < self.index <= dst:
                self.index -= 1
            elif dst <= self.index < src:
                self.index += 1
        self._emit_queue()

    def jump(self, index: int) -> None:
        self._start(index)

    def clear_queue(self) -> None:
        with self._lock:
            cur = self.current
            self.queue = [cur] if cur else []
            self.original = None
            self.index = 0 if cur else -1
        self._emit_queue()

    def _apply_shuffle(self, keep_index: int) -> None:
        self.original = list(self.queue)
        current = self.queue[keep_index]
        rest = [t for i, t in enumerate(self.queue) if i != keep_index]
        random.shuffle(rest)
        self.queue = [current] + rest
        self.index = 0
        self.shuffle = True

    def set_shuffle(self, enabled: bool) -> None:
        with self._lock:
            if enabled == self.shuffle:
                return
            if enabled and self.queue:
                self._apply_shuffle(max(self.index, 0))
            elif not enabled:
                if self.original is not None:
                    cur = self.current
                    self.queue = self.original
                    self.index = next((i for i, t in enumerate(self.queue) if cur and t["qid"] == cur["qid"]), 0)
                self.original = None
                self.shuffle = False
            self.shuffle = enabled
        self._emit_queue()

    # -- likes -------------------------------------------------------------
    def set_liked(self, track: dict, liked: bool) -> None:
        self.library.set_liked(track, liked)
        if self.ytm.authenticated:
            threading.Thread(target=lambda: self._rate(track["videoId"], liked), daemon=True).start()
        self._emit_state()

    def _rate(self, video_id: str, liked: bool) -> None:
        try:
            self.ytm.rate(video_id, liked)
        except Exception:
            pass

    # -- session persistence ----------------------------------------------
    def save_session(self) -> None:
        with self._lock:
            data = {"queue": self.queue, "original": self.original, "index": self.index, "pos": self.pos,
                    "title": self.title, "shuffle": self.shuffle, "repeat": self.repeat}
        try:
            self._session_path.write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            pass
        try:
            self.settings.update({"volume": self.volume})
        except OSError:
            pass

    def restore_session(self) -> None:
        if not self.settings.get("restore_session"):
            return
        try:
            data = json.loads(self._session_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        with self._lock:
            self.queue = [self._entry(t) for t in data.get("queue") or [] if t.get("videoId")]
            if data.get("original"):
                by_vid = {}
                for t in self.queue:
                    by_vid.setdefault(t["videoId"], t)
                self.original = [by_vid[t["videoId"]] for t in data["original"] if t.get("videoId") in by_vid]
            self.index = min(int(data.get("index", -1)), len(self.queue) - 1)
            self.pos = float(data.get("pos") or 0)
            self.title = data.get("title") or ""
            self.shuffle = bool(data.get("shuffle")) and self.original is not None
            self.repeat = data.get("repeat") if data.get("repeat") in REPEAT_MODES else "off"
            if self.current:
                self.duration = self.current.get("duration") or 0
        self._emit_queue()
