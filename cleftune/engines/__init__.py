"""Audio output engines. All of them play the local relay URL (/api/stream/<id>).

native  FFmpeg (PyAV) + miniaudio inside the app: default, bundled in installers, keeps playing
        with every window closed.
mpv     system libmpv, when installed (source installs).
web     the UI's <audio> element; last resort, stops when the window/tab closes.
"""

from __future__ import annotations

import importlib.util
import os
import sys

from ..config import IS_WINDOWS, data_dir


def native_available() -> bool:
    return bool(importlib.util.find_spec("av") and importlib.util.find_spec("miniaudio"))


def libmpv_available() -> bool:
    try:
        prepare_libmpv_search_path()
        import mpv  # noqa: F401  (loads libmpv on import)
        return True
    except (OSError, ImportError, AttributeError):
        return False


def prepare_libmpv_search_path() -> None:
    """On Windows, look for libmpv-2.dll in the app data folder and next to the executable."""
    if not IS_WINDOWS:
        return
    for folder in (data_dir() / "mpv", os.path.dirname(sys.executable)):
        if os.path.isdir(folder):
            os.environ["PATH"] = f"{folder}{os.pathsep}{os.environ.get('PATH', '')}"
            try:
                os.add_dll_directory(str(folder))
            except (OSError, AttributeError):
                pass


def engine_order(preference: str) -> list[str]:
    """Engines to try, best first. An explicit choice still falls back if it can't start."""
    order = {"native": ["native", "mpv", "web"], "mpv": ["mpv", "native", "web"], "web": ["web"]}
    return order.get(preference, ["native", "mpv", "web"])
