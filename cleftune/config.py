"""Per-OS paths, install locations, and persisted user settings."""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
FROZEN = bool(getattr(sys, "frozen", False))      # running from an installer build (PyInstaller)

MAC_SUPPORT_DIR = Path("/Library/Application Support/ClefTune")   # written by the .pkg installer


def _windows_base() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "ClefTune"


def _migrate(old: Path, new: Path) -> None:
    """The app used to be called Metrolist Desktop: carry the old library/cache over once."""
    if new.exists() or not old.is_dir():
        return
    try:
        if (old / "venv").exists():
            # an old from-source install still lives there: move the data, leave its Python environment
            new.mkdir(parents=True)
            for child in old.iterdir():
                if child.name != "venv":
                    child.rename(new / child.name)
        else:
            old.rename(new)
    except OSError:
        pass


def data_dir() -> Path:
    override = os.environ.get("CLEFTUNE_DATA_DIR")
    if override:
        path = Path(override)
    elif IS_WINDOWS:
        path = _windows_base()
        _migrate(path.parent / "MetrolistDesktop", path)
    elif IS_MAC:
        path = Path.home() / "Library" / "Application Support" / "ClefTune"
        _migrate(path.parent / "Metrolist Desktop", path)
    else:
        path = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "cleftune"
        _migrate(path.parent / "metrodesk", path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    if os.environ.get("CLEFTUNE_DATA_DIR"):
        path = data_dir() / "cache"
    elif IS_WINDOWS:
        path = _windows_base() / "cache"
    elif IS_MAC:
        path = Path.home() / "Library" / "Caches" / "ClefTune"
        _migrate(path.parent / "Metrolist Desktop", path)
    else:
        path = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "cleftune"
        _migrate(path.parent / "metrodesk", path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_download_dir() -> Path:
    return Path.home() / "Music" / "ClefTune"


def app_dir() -> Path:
    """Folder holding the app executable (installer builds) or the source package."""
    return Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent


def install_marker_paths() -> list[Path]:
    """Where installers record the user's choices (install.json)."""
    here = app_dir()
    return [here / "install.json", here.parent / "install.json", MAC_SUPPORT_DIR / "install.json"]


def read_install_marker() -> dict:
    for path in install_marker_paths():
        try:
            return json.loads(path.read_text(encoding="utf-8")) | {"_path": str(path)}
        except (OSError, ValueError):
            continue
    return {}


DEFAULTS: dict = {
    "ui_mode": "window",         # window | browser
    "engine": "auto",            # auto | native | mpv | web
    "close_to_background": True,  # closing the window keeps the music playing
    "cache_enabled": True,       # keep recently played songs for offline listening
    "cache_songs": 50,           # how many recently played songs to keep
    "audio_quality": "high",     # high | medium | low
    "prefer_m4a": IS_MAC,        # AAC streams; Safari's WebKit is happiest with them
    "normalize": False,          # loudness normalization (mpv engine only)
    "autoplay": True,            # keep playing related songs when the queue ends
    "skip_on_error": True,
    "theme": "dark",             # dark | light | system
    "dynamic_color": True,       # accent color taken from the album art
    "lyrics_words": "auto",      # auto (estimate when needed) | exact (source timing only) | off
    "language": "en",
    "location": "",              # two-letter region code, empty = automatic
    "download_dir": "",          # empty = default_download_dir()
    "use_account_for_playback": False,
    "volume": 80,
    "restore_session": True,
    "install_stamp": 0,          # last installer run whose choices were applied
}


class Settings:
    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / "settings.json"
        self._lock = threading.Lock()
        self._values = dict(DEFAULTS)
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
            self._values.update({k: v for k, v in stored.items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass

    def get(self, key: str):
        with self._lock:
            return self._values[key]

    def all(self) -> dict:
        with self._lock:
            return dict(self._values)

    def update(self, patch: dict) -> dict:
        with self._lock:
            for key, value in patch.items():
                if key not in DEFAULTS:
                    raise KeyError(f"Unknown setting: {key}")
                expected = type(DEFAULTS[key])
                if expected is int and isinstance(value, float):
                    value = int(value)
                if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
                    raise TypeError(f"Setting {key} must be {expected.__name__}")
                self._values[key] = value
            self._save_locked()
            return dict(self._values)

    def apply_install_choices(self) -> None:
        """Each installer run (install, modify, add window) records a choice once; later the
        in-app setting wins until the installer is run again."""
        marker = read_install_marker()
        stamp = int(marker.get("stamp") or 0)
        if stamp and stamp != self.get("install_stamp"):
            patch = {"install_stamp": stamp}
            if marker.get("ui_mode") in ("window", "browser"):
                patch["ui_mode"] = marker["ui_mode"]
            self.update(patch)

    def download_dir(self, create: bool = False) -> Path:
        custom = self.get("download_dir")
        path = Path(custom).expanduser() if custom else default_download_dir()
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def _save_locked(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._values, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
