"""Song cache: keeps the most recently played songs on disk so they play offline (and instantly).

Unlike Downloads (user-chosen, permanent, tagged files in Music/), the cache is automatic,
limited to the N most recently played songs, and lives in the app's cache folder.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

from .config import cache_dir
from .events import EventBus
from .library import Library
from .streams import StreamResolver, open_range

CHUNK = 1024 * 1024


class SongCache:
    def __init__(self, library: Library, resolver: StreamResolver, settings, bus: EventBus):
        self.library, self.resolver, self.settings, self.bus = library, resolver, settings, bus
        self.folder = cache_dir() / "songs"
        self.folder.mkdir(parents=True, exist_ok=True)
        self._jobs: queue.Queue = queue.Queue()
        self._queued: set[str] = set()
        self._lock = threading.Lock()
        self.current: str | None = None          # never evict the song that's playing
        threading.Thread(target=self._worker, name="song-cache", daemon=True).start()
        self._cleanup_orphans()

    def lookup(self, video_id: str) -> str | None:
        path = self.library.cache_path(video_id)
        if path and Path(path).is_file():
            return path
        return None

    def played(self, track: dict) -> None:
        """Called when a song starts playing."""
        video_id = track["videoId"]
        self.current = video_id
        if not self.settings.get("cache_enabled"):
            return
        self.library.cache_touch(video_id)
        if self.lookup(video_id) or self.library.download_path(video_id):
            self.evict()
            return
        with self._lock:
            if video_id in self._queued:
                return
            self._queued.add(video_id)
        self._jobs.put(video_id)

    def _worker(self) -> None:
        while True:
            video_id = self._jobs.get()
            try:
                self._fill(video_id)
            except Exception:
                pass                                # offline / unavailable: try again next time it plays
            finally:
                with self._lock:
                    self._queued.discard(video_id)
            self.evict()
            self.bus.emit("cache", {"changed": True})

    def _fill(self, video_id: str) -> None:
        info = self.resolver.resolve(video_id)
        if info.path:
            return
        target = self.folder / f"{video_id}.{info.ext}"
        partial = target.with_suffix(target.suffix + ".part")
        pos, total = 0, None
        with open(partial, "wb") as out:
            while total is None or pos < total:
                info, resp = open_range(self.resolver, video_id, info, pos, pos + CHUNK - 1)
                with resp:
                    if total is None:
                        total = int(resp.headers.get("Content-Range", "/0").rsplit("/", 1)[-1] or 0)
                        if not total:
                            raise RuntimeError("unknown size")
                    data = resp.read()
                if not data:
                    raise RuntimeError("stream ended early")
                out.write(data)
                pos += len(data)
        partial.replace(target)
        self.library.cache_set_file(video_id, str(target), total)

    def evict(self) -> None:
        limit = max(0, int(self.settings.get("cache_songs")))
        for i, entry in enumerate(self.library.cache_entries()):
            if i < limit or entry["video_id"] == self.current:
                continue
            if entry["path"]:
                Path(entry["path"]).unlink(missing_ok=True)
            self.library.cache_forget(entry["video_id"])

    def _cleanup_orphans(self) -> None:
        known = {Path(e["path"]).name for e in self.library.cache_entries() if e["path"]}
        for f in self.folder.iterdir():
            if f.name not in known:
                f.unlink(missing_ok=True)

    def clear(self) -> None:
        for entry in self.library.cache_entries():
            if entry["path"] and entry["video_id"] != self.current:
                Path(entry["path"]).unlink(missing_ok=True)
                self.library.cache_forget(entry["video_id"])

    def stats(self) -> dict:
        tracks = self.library.cached_tracks()
        return {"count": len(tracks), "bytes": sum(t.get("size") or 0 for t in tracks),
                "limit": self.settings.get("cache_songs"), "enabled": self.settings.get("cache_enabled"),
                "folder": str(self.folder)}
