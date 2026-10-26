"""Offline downloads with yt-dlp. With ffmpeg installed, files are tagged and get cover art."""

from __future__ import annotations

import os
import queue
import re
import shutil
import threading
import time
from pathlib import Path

import yt_dlp

from .events import EventBus
from .library import Library
from .streams import StreamResolver

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def safe_name(text: str, limit: int = 120) -> str:
    return _UNSAFE.sub("_", text).strip(" .")[:limit] or "track"


class DownloadManager:
    def __init__(self, library: Library, resolver: StreamResolver, settings, bus: EventBus):
        self.library, self.resolver, self.settings, self.bus = library, resolver, settings, bus
        self._queue: queue.Queue = queue.Queue()
        self._cancelled: set[str] = set()
        self._last_emit = 0.0
        self.ffmpeg = shutil.which("ffmpeg")
        self._worker = threading.Thread(target=self._run, name="downloads", daemon=True)
        self._worker.start()
        for video_id in library.reset_stale_downloads():
            self._queue.put(video_id)

    def add(self, tracks: list[dict]) -> int:
        added = 0
        done = set(self.library.download_ids())
        for track in tracks:
            if track["videoId"] in done:
                continue
            self.library.upsert(track)
            self.library.set_download(track["videoId"], "queued")
            self._cancelled.discard(track["videoId"])
            self._queue.put(track["videoId"])
            added += 1
        self._notify(force=True)
        return added

    def delete(self, video_id: str) -> None:
        self._cancelled.add(video_id)
        path = self.library.delete_download(video_id)
        if path:
            Path(path).unlink(missing_ok=True)
        self._notify(force=True)

    def _notify(self, force: bool = False) -> None:
        now = time.monotonic()
        if force or now - self._last_emit > 0.5:
            self._last_emit = now
            self.bus.emit("downloads", {"changed": True})

    def _run(self) -> None:
        while True:
            video_id = self._queue.get()
            if video_id is None:
                return
            if video_id in self._cancelled:
                continue
            try:
                self._download_with_retry(video_id)
            except Exception as exc:
                message = str(exc).replace("ERROR: ", "")
                self.library.set_download(video_id, "error", error=message[:300])
                self.bus.emit("toast", {"message": f"Download failed: {message[:120]}", "kind": "error"})
            self._notify(force=True)

    def _download_with_retry(self, video_id: str, attempts: int = 3) -> None:
        # googlevideo can briefly reject fresh URLs with 403; a new attempt usually succeeds
        for attempt in range(attempts):
            try:
                return self._download(video_id)
            except yt_dlp.utils.DownloadCancelled:
                return
            except yt_dlp.utils.DownloadError:
                if attempt == attempts - 1 or video_id in self._cancelled:
                    raise
                time.sleep(2 * (attempt + 1))

    def _download(self, video_id: str) -> None:
        track = self.library.song(video_id) or {"title": video_id, "artist": ""}
        folder = self.settings.download_dir(create=True)
        stem = safe_name(f"{track.get('artist') or 'Unknown'} - {track['title']} [{video_id}]")
        self.library.set_download(video_id, "downloading")
        final: dict = {}

        def progress(d):
            if video_id in self._cancelled:
                raise yt_dlp.utils.DownloadCancelled("cancelled")
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                pct = (d.get("downloaded_bytes", 0) / total) if total else 0
                self.library.set_download(video_id, "downloading", progress=round(pct, 3))
                self._notify()

        def post(path):
            final["path"] = path

        opts = self.resolver.ydl_options() | {
            "outtmpl": str(folder / f"{stem}.%(ext)s"), "progress_hooks": [progress],
            "post_hooks": [post], "overwrites": True,
        }
        if self.ffmpeg:
            opts["writethumbnail"] = True
            opts["postprocessors"] = [
                # Opus/AAC are remuxed, not re-encoded
                {"key": "FFmpegExtractAudio", "preferredcodec": "best"},
                {"key": "FFmpegMetadata", "add_metadata": True},
                {"key": "EmbedThumbnail"},
            ]
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://music.youtube.com/watch?v={video_id}", download=True)
            path = final.get("path") or ydl.prepare_filename(info)
        if video_id in self._cancelled:
            Path(path).unlink(missing_ok=True)
            return
        if not os.path.exists(path):
            raise RuntimeError("Downloaded file not found")
        self.library.set_download(video_id, "done", path=path, progress=1.0)

    def shutdown(self) -> None:
        self._queue.put(None)
