"""Application: wires the services together and shows the UI (own window or web browser)."""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from . import APP_NAME, __version__
from .api import Api
from .config import FROZEN, IS_LINUX, IS_MAC, IS_WINDOWS, MAC_SUPPORT_DIR, Settings, app_dir, data_dir
from .downloads import DownloadManager
from .engines import engine_order, libmpv_available, native_available
from .engines.web_engine import WebEngine
from .events import EventBus
from .library import Library
from .lyrics import LyricsService
from .player import Player
from .server import Server
from .song_cache import SongCache
from .streams import StreamResolver
from .ytm import YTM

log = logging.getLogger("cleftune")
INSTANCE_FILE = "instance.json"
VIEWER_STARTUP_GRACE = 20     # seconds: a window that dies sooner than this "failed to start"


def find_viewer() -> list[str] | None:
    """Command that starts the window add-on, or None when it isn't installed."""
    override = os.environ.get("CLEFTUNE_VIEWER")
    if override:
        return [override] if Path(override).is_file() else None
    if FROZEN:
        exe = "ClefTuneWindow.exe" if IS_WINDOWS else "ClefTuneWindow"
        here = app_dir()
        candidates = [here / "window" / exe, here.parent / "window" / exe]
        if IS_MAC:
            bundle = Path("ClefTune Window.app") / "Contents" / "MacOS" / "ClefTuneWindow"
            candidates += [MAC_SUPPORT_DIR / bundle,
                           Path.home() / "Library" / "Application Support" / "ClefTune" / bundle]
        return next(([str(c)] for c in candidates if c.is_file()), None)
    # running from source: the add-on is available when a window toolkit is installed
    if importlib.util.find_spec("webview") or importlib.util.find_spec("PySide6"):
        return [sys.executable, "-m", "cleftune.viewer"]
    return None


class App:
    def __init__(self, args):
        self.args = args
        self.settings = Settings()
        self.settings.apply_install_choices()
        self.bus = EventBus()
        self.library = Library()
        self.ytm = YTM(self.settings)
        self.resolver = StreamResolver(self.settings, self._local_audio, self.ytm.cookie_header, self.ytm.visitor_data)
        self.song_cache = SongCache(self.library, self.resolver, self.settings, self.bus)
        self.lyrics = LyricsService(self.ytm)
        self.player = Player(self.settings, self.library, self.ytm, self.resolver, self.bus)
        self.player.track_listeners.append(self.song_cache.played)
        self.downloads = DownloadManager(self.library, self.resolver, self.settings, self.bus)
        self.api = Api(self)
        self.server = Server(self.api, self.resolver, self.bus, port=args.port)
        self.window_mode = "none"           # window | browser (what is showing right now)
        self.mpris_active = False
        self.viewer: subprocess.Popen | None = None
        self._viewer_lock = threading.Lock()
        self._closing_viewers: set = set()  # viewers we closed on purpose (mode switch)
        self._quit = threading.Event()
        self._create_engine(args.engine or self.settings.get("engine"))

    def _local_audio(self, video_id: str) -> str | None:
        """Downloaded or cached copy of a song, if any (plays offline and instantly)."""
        return self.library.download_path(video_id) or self.song_cache.lookup(video_id)

    def _create_engine(self, preference: str) -> None:
        engine = None
        for name in engine_order(preference):
            try:
                if name == "native" and native_available():
                    from .engines.native_engine import NativeEngine
                    engine = NativeEngine(self.player.on_engine_event)
                elif name == "mpv" and libmpv_available():
                    from .engines.mpv_engine import MpvEngine
                    engine = MpvEngine(self.player.on_engine_event)
                elif name == "web":
                    engine = WebEngine(self.player.on_engine_event, self.bus)
            except Exception as exc:
                log.warning("%s audio engine unavailable (%s)", name, exc)
            if engine:
                break
        if engine.name == "web":
            url = self.server.stream_path
        else:
            def url(video_id, gen):
                return self.server.base_url + self.server.stream_path(video_id, gen)
        self.player.attach(engine, url)
        log.info("audio engine: %s", engine.name)

    @property
    def ui_url(self) -> str:
        return self.server.base_url + "/"

    @property
    def window_available(self) -> bool:
        return find_viewer() is not None

    # -- lifecycle --------------------------------------------------------
    def run(self) -> None:
        self.server.start()
        self._write_instance()
        self.player.restore_session()
        mode = "browser" if self.args.browser else "window" if self.args.window else self.settings.get("ui_mode")
        if IS_LINUX and (self.player.engine.name != "web" or mode == "window"):
            # media keys / desktop media panel; with the web engine in a browser tab the browser does it
            from .mpris import start_mpris
            self.mpris_active = start_mpris(self.player, self.bus, self.quit, self.raise_window)
        threading.Thread(target=self._autosave, daemon=True).start()
        threading.Thread(target=self._warm_up, daemon=True).start()
        log.info("UI at %s", self.ui_url)
        if not (mode == "window" and self.start_viewer()):
            if mode == "window":
                log.warning("window add-on not installed; opening the browser")
            self.open_browser()
        try:
            while not self._quit.wait(0.5):
                pass
        except KeyboardInterrupt:
            pass
        self.shutdown()

    def open_browser(self) -> None:
        self.window_mode = "browser"
        print(f"{APP_NAME} is running at {self.ui_url}\nUse Quit in the sidebar (or Ctrl+C) to stop it.", flush=True)
        webbrowser.open(self.ui_url)

    # -- window add-on ----------------------------------------------------
    def start_viewer(self) -> bool:
        cmd = find_viewer()
        if not cmd:
            return False
        try:
            proc = subprocess.Popen(cmd + ["--url", self.ui_url, "--token", self.server.token],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            log.warning("could not start the window: %s", exc)
            return False
        with self._viewer_lock:
            self.viewer = proc
        self.window_mode = "window"
        threading.Thread(target=self._watch_viewer, args=(proc, time.monotonic()), daemon=True).start()
        log.info("window started (%s)", cmd[0])
        return True

    def _watch_viewer(self, proc: subprocess.Popen, started: float) -> None:
        code = proc.wait()
        with self._viewer_lock:
            current = proc is self.viewer
            if current:
                self.viewer = None
            on_purpose = proc in self._closing_viewers
            self._closing_viewers.discard(proc)
        if not current or on_purpose or self._quit.is_set():
            return
        if code != 0 and time.monotonic() - started < VIEWER_STARTUP_GRACE:
            log.warning("window failed to start (exit %s, see window.log); opening the browser", code)
            self.open_browser()
            return
        if self.player.engine.name == "web":
            self.quit()      # last-resort engine: the audio lived in that window
        else:
            self.window_mode = "background"
            log.info("window closed; still playing in the background")

    def close_viewer(self) -> None:
        with self._viewer_lock:
            proc, self.viewer = self.viewer, None
            if proc:
                self._closing_viewers.add(proc)
        if not proc:
            return
        self.bus.emit("window", {"cmd": "close"})
        try:
            proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            proc.terminate()

    def viewer_running(self) -> bool:
        with self._viewer_lock:
            return self.viewer is not None and self.viewer.poll() is None

    def switch_ui(self, mode: str) -> dict:
        if mode not in ("window", "browser"):
            raise ValueError("mode must be window or browser")
        if mode == "window":
            if self.viewer_running():
                self.raise_window()
            elif not self.start_viewer():
                return {"ok": False, "mode": self.window_mode,
                        "message": "The separate window isn't installed. " + window_install_hint()}
        else:
            self.open_browser()
            self.close_viewer()
        self.settings.update({"ui_mode": mode})
        return {"ok": True, "mode": mode}

    def raise_window(self) -> None:
        if self.viewer_running():
            self.bus.emit("window", {"cmd": "raise"})
        elif self.settings.get("ui_mode") == "window" and self.start_viewer():
            pass
        else:
            self.open_browser()

    def quit(self) -> None:
        self._quit.set()
        threading.Thread(target=self.close_viewer, daemon=True).start()

    def _warm_up(self) -> None:
        """Get the likely first action ready: resuming the restored song (and the one after it)."""
        try:
            self.ytm.visitor_data()
        except Exception:
            return            # offline
        with self.player._lock:
            upcoming = [t["videoId"] for t in self.player.queue[max(self.player.index, 0):self.player.index + 2]]
        self.player.prefetch(upcoming)
        self.resolver.warm_up()

    def _autosave(self) -> None:
        while not self._quit.wait(30):
            self.player.save_session()

    def shutdown(self) -> None:
        self.close_viewer()
        self.player.save_session()
        for step in (self.player.engine.shutdown, self.downloads.shutdown, self.resolver.shutdown,
                     self.server.stop, self.library.close):
            try:
                step()
            except Exception:
                pass
        instance = data_dir() / INSTANCE_FILE
        try:
            if json.loads(instance.read_text(encoding="utf-8")).get("port") == self.server.port:
                instance.unlink()
        except (OSError, ValueError):
            pass

    def _write_instance(self) -> None:
        (data_dir() / INSTANCE_FILE).write_text(json.dumps({"port": self.server.port, "token": self.server.token}),
                                                encoding="utf-8")


def window_install_hint() -> str:
    if not FROZEN:
        return "Install pywebview (Windows/macOS) or PySide6 (Linux) into the app's Python environment."
    if IS_WINDOWS:
        return "Run the ClefTune setup again and choose \"Own window\"."
    if IS_MAC:
        return "Open the ClefTune installer (.pkg) again, click Customize and tick \"Separate window\"."
    return "Run the ClefTune installer (.run) again and choose \"Add the separate window\"."


def _signal_running_instance() -> bool:
    """If another instance is running, ask it to show itself and return True."""
    try:
        info = json.loads((data_dir() / INSTANCE_FILE).read_text(encoding="utf-8"))
        req = urllib.request.Request(f"http://127.0.0.1:{info['port']}/api/call/raise_window", data=b"{}",
                                     headers={"X-Token": info["token"], "Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="cleftune", description=f"{APP_NAME} {__version__}")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--browser", action="store_true", help="open in your web browser this time")
    mode.add_argument("--window", action="store_true", help="open in its own window this time")
    parser.add_argument("--engine", choices=["auto", "native", "mpv", "web"], help="audio engine for this run")
    parser.add_argument("--port", type=int, default=0, help="local port (default: random)")
    parser.add_argument("--debug", action="store_true", help="verbose logs")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    handlers: list[logging.Handler] = [logging.FileHandler(data_dir() / "cleftune.log", encoding="utf-8")]
    if sys.stderr and (args.debug or not IS_WINDOWS):
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if _signal_running_instance():
        print(f"{APP_NAME} is already running; switched to it.")
        return
    app = App(args)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, lambda *_: app.quit())
    app.run()
