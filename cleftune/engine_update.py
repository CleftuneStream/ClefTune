"""Updatable YouTube engine for installer builds.

YouTube changes frequently and old yt-dlp versions stop working, but a frozen app can't
pip-upgrade. This downloads newer yt-dlp / yt-dlp-ejs wheels from PyPI (SHA-256 verified),
test-imports them in a separate process, and swaps them in. An import hook then prefers
them over the bundled copies on the next start.
"""

from __future__ import annotations

import hashlib
import importlib.abc
import importlib.machinery
import json
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

from .config import FROZEN, data_dir

PACKAGES = {"yt-dlp": "yt_dlp", "yt-dlp-ejs": "yt_dlp_ejs"}   # PyPI name -> import name
_TOP_LEVEL = set(PACKAGES.values())


def engine_root() -> Path:
    return data_dir() / "engine"


def current_dir() -> Path:
    return engine_root() / "current"


class _OverrideFinder(importlib.abc.MetaPathFinder):
    """Loads yt_dlp (and every submodule) from `root` ahead of the frozen/bundled copy."""

    def __init__(self, root: Path):
        self.root = str(root)

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] not in _TOP_LEVEL:
            return None
        search = [self.root] if "." not in fullname else path
        return importlib.machinery.PathFinder.find_spec(fullname, search)


def _activate_dir(root: Path) -> bool:
    if not (root / "yt_dlp" / "__init__.py").is_file():
        return False
    if any(name in sys.modules for name in _TOP_LEVEL):
        return False  # too late, the bundled copy is already loaded
    sys.meta_path.insert(0, _OverrideFinder(root))
    return True


def activate() -> bool:
    """Call before anything imports yt_dlp."""
    return _activate_dir(current_dir())


def check_engine(root: str) -> int:
    """Run in a child process: prove the staged engine imports and initialises."""
    if not _activate_dir(Path(root)):
        print("not an engine folder", file=sys.stderr)
        return 2
    import yt_dlp
    import yt_dlp_ejs  # noqa: F401
    with yt_dlp.YoutubeDL({"quiet": True}):
        pass
    print(yt_dlp.version.__version__)
    return 0


def status() -> dict:
    import yt_dlp
    overridden = current_dir().is_dir() and Path(yt_dlp.__file__).resolve().is_relative_to(current_dir().resolve())
    return {"version": yt_dlp.version.__version__, "updated": overridden, "staged": _staged_version()}


def _staged_version() -> str | None:
    try:
        return json.loads((current_dir() / "ENGINE.json").read_text())["yt-dlp"]
    except (OSError, ValueError, KeyError):
        return None


def _latest_wheel(project: str) -> tuple[str, str, str]:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{project}/json", timeout=20) as resp:
        data = json.load(resp)
    version = data["info"]["version"]
    for f in data["urls"]:
        if f["packagetype"] == "bdist_wheel" and f["filename"].endswith("py3-none-any.whl"):
            return version, f["url"], f["digests"]["sha256"]
    raise RuntimeError(f"No pure-Python wheel published for {project} {version}")


def _version_key(v: str) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in v.replace("-", ".").split("."))


def _extract_wheel(url: str, sha256: str, dest: Path, package: str) -> None:
    with urllib.request.urlopen(url, timeout=60) as resp:
        blob = resp.read()
    if hashlib.sha256(blob).hexdigest() != sha256:
        raise RuntimeError("Downloaded engine failed its checksum; nothing was changed.")
    wheel = dest / "wheel.zip"
    wheel.write_bytes(blob)
    with zipfile.ZipFile(wheel) as zf:
        for name in zf.namelist():
            if not name.startswith(package + "/"):
                continue
            target = (dest / name).resolve()
            if not target.is_relative_to(dest.resolve()):
                raise RuntimeError("Unsafe path in wheel")
            zf.extract(name, dest)
    wheel.unlink()


def _self_command() -> list[str]:
    return [sys.executable] if FROZEN else [sys.executable, "-m", "cleftune"]


def update() -> dict:
    """Fetch the newest engine if it's newer than the running one. Needs a restart to apply."""
    running = status()
    latest, url, sha = _latest_wheel("yt-dlp")
    newest_known = max(running["version"], running["staged"] or "0", key=_version_key)
    if _version_key(latest) <= _version_key(newest_known):
        return {"updated": False, "version": newest_known, "message": f"Already up to date ({newest_known})."}

    root = engine_root()
    root.mkdir(parents=True, exist_ok=True)
    staging = root / f"staging-{int(time.time())}"
    staging.mkdir()
    try:
        _extract_wheel(url, sha, staging, "yt_dlp")
        ejs_version, ejs_url, ejs_sha = _latest_wheel("yt-dlp-ejs")
        _extract_wheel(ejs_url, ejs_sha, staging, "yt_dlp_ejs")
        check = subprocess.run(_self_command() + ["--check-engine", str(staging)], capture_output=True, text=True,
                               timeout=120, stdin=subprocess.DEVNULL)
        if check.returncode != 0 or check.stdout.strip() != latest:
            raise RuntimeError(f"The new engine failed its self-test: {(check.stderr or check.stdout).strip()[-300:]}")
        (staging / "ENGINE.json").write_text(json.dumps({"yt-dlp": latest, "yt-dlp-ejs": ejs_version}))
        old = root / f"old-{int(time.time())}"
        if current_dir().exists():
            current_dir().rename(old)
        staging.rename(current_dir())
        shutil.rmtree(old, ignore_errors=True)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return {"updated": True, "version": latest, "message": f"YouTube engine {latest} installed. Restart to use it."}


def reset() -> None:
    shutil.rmtree(current_dir(), ignore_errors=True)
