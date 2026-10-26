"""Turns a videoId into a playable audio source: a downloaded/cached file, or a YouTube stream URL.

Speed matters here (it's most of the time between "click" and "sound"):
* fast path: one player client, no watch-page download, shared visitor data, falls back to
  yt-dlp's full default flow when YouTube refuses it;
* yt-dlp instances are reused per thread (saves its ~0.5 s start-up);
* resolved URLs are remembered on disk until they expire, so replays skip the lookup;
* upcoming songs are resolved ahead of time and their first chunk is pre-downloaded.
"""

from __future__ import annotations

import collections
import json
import os
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import logging

import yt_dlp

from .config import Settings, cache_dir

QUALITY_FORMATS = {
    "high": "bestaudio",
    "medium": "bestaudio[abr<=130]/bestaudio",
    "low": "worstaudio/bestaudio",
}
EXPIRY_MARGIN = 10 * 60
HEAD_BYTES = 512 * 1024               # pre-downloaded start of upcoming songs
HEAD_SLOTS = 6
FAST_PATH_CLIENT = "tv_samsung"
log = logging.getLogger("cleftune.streams")
CONTENT_ERRORS = ("unavailable", "private", "removed", "copyright", "not available in your country",
                  "confirm your age", "members-only", "terminated")


@dataclass
class StreamInfo:
    video_id: str
    url: str | None = None          # remote media URL
    path: str | None = None         # local file (download or song cache)
    headers: dict = field(default_factory=dict)
    ext: str = "webm"
    codec: str | None = None
    bitrate: float | None = None
    size: int | None = None
    duration: float | None = None
    expires_at: float = float("inf")

    @property
    def mime(self) -> str:
        return {"webm": "audio/webm", "m4a": "audio/mp4", "mp4": "audio/mp4", "opus": "audio/ogg",
                "ogg": "audio/ogg", "mp3": "audio/mpeg", "mka": "audio/x-matroska"}.get(self.ext, "application/octet-stream")

    def describe(self) -> str:
        parts = [self.codec or self.ext, self.bitrate and f"{round(self.bitrate)} kbps", "offline" if self.path else None]
        return " • ".join(p for p in parts if p)


def detect_js_runtimes() -> dict:
    """yt-dlp needs a JavaScript runtime to solve YouTube's player challenges."""
    # keep Deno's own cache inside ours, so uninstalling leaves nothing behind
    os.environ.setdefault("DENO_DIR", str(cache_dir() / "deno"))
    runtimes: dict = {}
    bundled = Path(sys.executable).parent / ("deno.exe" if sys.platform.startswith("win") else "deno")
    if getattr(sys, "frozen", False) and bundled.is_file():   # installers ship deno next to the app
        runtimes["deno"] = {"path": str(bundled)}
    for name, binary in (("deno", "deno"), ("node", "node"), ("bun", "bun")):
        if name in runtimes:
            continue
        path = shutil.which(binary)
        if path:
            runtimes[name] = {"path": path}
    if "deno" not in runtimes:
        try:
            from deno import find_deno_bin
            runtimes["deno"] = {"path": find_deno_bin()}
        except Exception:
            pass
    return dict(sorted(runtimes.items(), key=lambda kv: kv[0] != "deno"))


class StreamError(Exception):
    pass


def open_range(resolver: "StreamResolver", video_id: str, info: StreamInfo, first: int, last: int):
    """GET one byte range of a stream, with recovery. Returns (info, response).

    YouTube refuses a freshly issued URL (403) for ~2 s before it starts working, so the same URL is
    polled quickly for a few seconds first; only then is a new URL resolved (covers real expiry).
    """
    delays = (0.25,) * 16
    attempt, refreshed = 0, False
    while True:
        req = urllib.request.Request(info.url, headers=dict(info.headers) | {"Range": f"bytes={first}-{last}"})
        try:
            return info, urllib.request.urlopen(req, timeout=20)
        except urllib.error.HTTPError as exc:
            if not (exc.code in (403, 410, 429) or exc.code >= 500):
                raise
            if attempt < len(delays):
                time.sleep(delays[attempt])
                attempt += 1
                continue
            if refreshed:
                raise
            resolver.invalidate(video_id)
            info = resolver.resolve(video_id)
            if info.path:
                raise StreamError("stream became local")
            attempt, refreshed = 0, True
        except (TimeoutError, ConnectionError, urllib.error.URLError):
            if attempt >= len(delays):
                raise
            time.sleep(delays[attempt])
            attempt += 1


@dataclass
class Head:
    data: bytes
    total: int


class StreamResolver:
    def __init__(self, settings: Settings, local_path_lookup, cookie_provider=None, visitor_provider=None):
        self.settings = settings
        self.local_path_lookup = local_path_lookup   # videoId -> path | None (downloads, song cache)
        self.cookie_provider = cookie_provider       # () -> "Cookie" header | None
        self.visitor_provider = visitor_provider     # () -> visitor data | None
        self.js_runtimes = detect_js_runtimes()
        self._cache: dict[str, StreamInfo] = {}
        self._pending: dict[str, Future] = {}
        self._heads: collections.OrderedDict[str, Head] = collections.OrderedDict()
        self._head_jobs: set[str] = set()
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="resolve")
        self._head_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="stream-head")
        self._tls = threading.local()
        self._opts_gen = 0
        self._fast_failures = 0
        self._fast_off_until = 0.0
        self._cookie_file = cache_dir() / "cookies.txt"
        self._disk_path = cache_dir() / "streams.json"
        self._load_disk()

    # -- public API -------------------------------------------------------
    def resolve(self, video_id: str, timeout: float = 60) -> StreamInfo:
        local = self.local_path_lookup(video_id)
        if local and Path(local).exists():
            p = Path(local)
            return StreamInfo(video_id, path=str(p), ext=p.suffix.lstrip(".").lower(), size=p.stat().st_size)
        return self._future(video_id).result(timeout=timeout)

    def prefetch(self, video_id: str, head: bool = True) -> None:
        if self.local_path_lookup(video_id):
            return
        self._future(video_id)      # the first chunk is fetched automatically once resolved

    def get_head(self, video_id: str, wait: float = 0.0) -> Head | None:
        """The pre-downloaded first chunk; optionally wait for a warm-up that's already running."""
        deadline = time.monotonic() + wait
        while True:
            with self._lock:
                head = self._heads.get(video_id)
                running = video_id in self._head_jobs
            if head or not running or time.monotonic() >= deadline:
                return head
            time.sleep(0.05)

    def invalidate(self, video_id: str) -> None:
        with self._lock:
            self._cache.pop(video_id, None)
            self._heads.pop(video_id, None)
        self._save_disk()

    def clear(self) -> None:
        """Settings changed (quality, account): forget URLs and rebuild yt-dlp instances."""
        with self._lock:
            self._cache.clear()
            self._heads.clear()
            self._opts_gen += 1
        self._save_disk()

    # -- futures & caching ------------------------------------------------
    def _future(self, video_id: str) -> Future:
        with self._lock:
            cached = self._cache.get(video_id)
            if cached and cached.expires_at > time.time():
                done: Future = Future()
                done.set_result(cached)
                return done
            pending = self._pending.get(video_id)
            if pending:
                return pending
            future = self._pool.submit(self._extract, video_id)
            self._pending[video_id] = future

        def finished(f: Future):
            with self._lock:
                self._pending.pop(video_id, None)
                if not f.exception():
                    self._cache[video_id] = f.result()
            if not f.exception():
                self._save_disk()
                # start YouTube's ~2 s URL warm-up right away and keep the first chunk ready
                self._prefetch_head(video_id, f.result())
        future.add_done_callback(finished)
        return future

    def _load_disk(self) -> None:
        try:
            data = json.loads(self._disk_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        now = time.time()
        if data.get("key") != self._settings_key():
            return
        for vid, raw in data.get("streams", {}).items():
            if raw.get("expires_at", 0) > now:
                self._cache[vid] = StreamInfo(**raw)

    def _save_disk(self) -> None:
        with self._lock:
            now = time.time()
            streams = {vid: asdict(info) for vid, info in self._cache.items() if info.url and info.expires_at > now}
        try:
            tmp = self._disk_path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"key": self._settings_key(), "streams": streams}), encoding="utf-8")
            tmp.replace(self._disk_path)
        except OSError:
            pass

    def _settings_key(self) -> str:
        return f"{self.settings.get('audio_quality')}|{self.settings.get('prefer_m4a')}|" \
               f"{self.settings.get('use_account_for_playback')}"

    def _prefetch_head(self, video_id: str, info: StreamInfo) -> None:
        with self._lock:
            if video_id in self._heads or video_id in self._head_jobs or not info.url:
                return
            self._head_jobs.add(video_id)

        def job():
            try:
                info2, resp = open_range(self, video_id, info, 0, HEAD_BYTES - 1)
                with resp:
                    data = resp.read()
                    total = int(resp.headers.get("Content-Range", "/0").rsplit("/", 1)[-1] or 0)
                if data and total:
                    with self._lock:
                        self._heads[video_id] = Head(data, total)
                        while len(self._heads) > HEAD_SLOTS:
                            self._heads.popitem(last=False)
            except Exception:
                pass
            finally:
                with self._lock:
                    self._head_jobs.discard(video_id)
        self._head_pool.submit(job)

    # -- yt-dlp ---------------------------------------------------------------
    def ydl_options(self, fmt: str | None = None, fast: bool = False) -> dict:
        quality = QUALITY_FORMATS.get(self.settings.get("audio_quality"), "bestaudio")
        if self.settings.get("prefer_m4a"):
            quality = "bestaudio[ext=m4a]/" + quality
        youtube_args = {"skip": ["hls", "dash", "translated_subs"]}
        opts = {
            "quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True,
            "format": fmt or quality, "socket_timeout": 20, "cachedir": str(cache_dir() / "yt-dlp"),
            "extractor_args": {"youtube": youtube_args},
        }
        if self.js_runtimes:
            opts["js_runtimes"] = self.js_runtimes
        cookies = self._cookie_path()
        if cookies:
            opts["cookiefile"] = str(cookies)
        elif fast:
            youtube_args.update({"player_client": [FAST_PATH_CLIENT], "player_skip": ["webpage", "configs"],
                                 "visitor_data": [self._visitor_data()]})
        return opts

    def _visitor_data(self) -> str | None:
        try:
            return self.visitor_provider() if self.visitor_provider else None
        except Exception:
            return None

    def _fast_allowed(self) -> bool:
        return (not self._cookie_path() and time.time() >= self._fast_off_until and bool(self._visitor_data()))

    def _ydl(self, fast: bool) -> yt_dlp.YoutubeDL:
        key = (fast, self._opts_gen)
        if getattr(self._tls, "key", None) != key:
            old = getattr(self._tls, "ydl", None)
            if old:
                old.close()
            self._tls.ydl = yt_dlp.YoutubeDL(self.ydl_options(fast=fast))
            self._tls.key = key
        return self._tls.ydl

    def _cookie_path(self) -> Path | None:
        if not (self.settings.get("use_account_for_playback") and self.cookie_provider):
            return None
        header = self.cookie_provider()
        if not header:
            return None
        lines = ["# Netscape HTTP Cookie File"]
        expiry = str(int(time.time()) + 30 * 86400)
        for pair in header.split(";"):
            if "=" not in pair:
                continue
            name, value = pair.strip().split("=", 1)
            lines.append("\t".join([".youtube.com", "TRUE", "/", "TRUE", expiry, name, value]))
        self._cookie_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return self._cookie_file

    def _extract(self, video_id: str) -> StreamInfo:
        url = f"https://music.youtube.com/watch?v={video_id}"
        started = time.monotonic()
        if self._fast_allowed():
            try:
                info = self._ydl(fast=True).extract_info(url, download=False)
                self._fast_failures = 0
                log.info("resolved %s via fast path in %.2fs", video_id, time.monotonic() - started)
                return self._to_stream(video_id, info)
            except yt_dlp.utils.DownloadError as exc:
                message = self._clean_error(exc)
                log.info("fast path failed for %s after %.2fs: %s", video_id, time.monotonic() - started, message[:120])
                if any(k in message.lower() for k in CONTENT_ERRORS):
                    raise StreamError(message) from None
                self._fast_failures += 1
                if self._fast_failures >= 3:   # YouTube changed something: use the full flow for a while
                    self._fast_off_until = time.time() + 30 * 60
                    self._fast_failures = 0
        try:
            info = self._ydl(fast=False).extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as exc:
            raise StreamError(self._clean_error(exc)) from None
        log.info("resolved %s via full flow in %.2fs", video_id, time.monotonic() - started)
        return self._to_stream(video_id, info)

    @staticmethod
    def _clean_error(exc: Exception) -> str:
        message = str(exc).replace("ERROR: ", "")
        if "[youtube]" in message:
            message = message.split(":", 1)[-1].strip()
        return message

    @staticmethod
    def _to_stream(video_id: str, info: dict) -> StreamInfo:
        if info.get("requested_formats"):
            info = info["requested_formats"][0] | {"duration": info.get("duration")}
        media_url = info.get("url")
        if not media_url:
            raise StreamError("No playable audio stream found.")
        expire = parse_qs(urlparse(media_url).query).get("expire", [None])[0]
        expires_at = float(expire) - EXPIRY_MARGIN if expire and expire.isdigit() else time.time() + 3600
        return StreamInfo(
            video_id=video_id, url=media_url, headers=dict(info.get("http_headers") or {}),
            ext=info.get("ext") or "webm", codec=info.get("acodec"), bitrate=info.get("abr") or info.get("tbr"),
            size=info.get("filesize"), duration=info.get("duration"), expires_at=expires_at,
        )

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
        self._head_pool.shutdown(wait=False, cancel_futures=True)
