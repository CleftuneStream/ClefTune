"""Build the installer for the operating system this runs on.

    python -m pip install -r packaging/requirements-build.txt
    python packaging/build.py

Output: dist/installers/
    Windows  ClefTune-<ver>-windows-x64-setup.exe     (needs Inno Setup 6: iscc)
    Linux    ClefTune-<ver>-linux-<arch>.run
    macOS    ClefTune-<ver>-macos-<arch>.pkg

Every installer carries its own Python runtime, libraries and JavaScript engine (Deno), so the
target machine needs nothing pre-installed. The app is built as two parts: the core (player +
browser UI) and the optional window add-on, which installers offer as a choice.

PyInstaller can't cross-compile: build each installer on its own OS (the GitHub workflow in
.github/workflows/installers.yml does all three).
"""

from __future__ import annotations

import argparse
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"
WEB = ROOT / "cleftune" / "web"
BUILD = ROOT / "build"
DIST = ROOT / "dist"
VERSION = re.search(r'__version__ = "([^"]+)"', (ROOT / "cleftune" / "__init__.py").read_text()).group(1)

IS_WIN, IS_MAC = sys.platform.startswith("win"), sys.platform == "darwin"
OS_NAME = "windows" if IS_WIN else "macos" if IS_MAC else "linux"
ARCH = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}.get(platform.machine().lower(),
                                                                                         platform.machine().lower())
CORE, WINDOW = "ClefTune", "ClefTuneWindow"
APP_ID = "io.github.cleftune"


def run(cmd: list, **kw) -> None:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def pyinstaller(name: str, script: Path, extra: list) -> Path:
    icon = WEB / ("icon.ico" if IS_WIN else "icon.icns" if IS_MAC else "icon.png")
    args = [
        sys.executable, "-m", "PyInstaller", str(script), "--name", name, "--noconfirm", "--clean", "--windowed",
        "--paths", str(ROOT), "--icon", str(icon),
        "--add-data", f"{WEB}{os.pathsep}cleftune/web",
        "--distpath", str(BUILD / "dist"), "--workpath", str(BUILD / "work"), "--specpath", str(BUILD / "spec"),
        "--exclude-module", "tkinter",
    ]
    if IS_MAC:
        args += ["--osx-bundle-identifier", f"{APP_ID}.{name.lower()}"]
    elif not IS_WIN:
        args += ["--strip"]                # drop debug symbols: the FFmpeg libs alone shrink by ~30 MB
    run(args + extra)
    return BUILD / "dist" / (f"{name}.app" if IS_MAC else name)


def build_core() -> Path:
    return pyinstaller(CORE, PACKAGING / "launcher.py", [
        "--collect-submodules", "cleftune",
        "--collect-submodules", "yt_dlp",      # extractors are imported lazily
        "--collect-all", "yt_dlp_ejs",         # YouTube challenge solver scripts
        "--collect-data", "ytmusicapi",        # locale files
        "--collect-all", "av",                 # FFmpeg decoder for the native audio engine
        "--hidden-import", "_miniaudio",
        # not used by installer builds (python-mpv's hook would drag in libmpv and its whole tree)
        "--exclude-module", "mpv", "--exclude-module", "PIL",
        "--exclude-module", "webview", "--exclude-module", "PySide6", "--exclude-module", "gi",
    ])


def build_window() -> Path:
    extra = ["--exclude-module", "yt_dlp", "--exclude-module", "ytmusicapi", "--exclude-module", "mpv",
             "--exclude-module", "av", "--exclude-module", "miniaudio"]
    if IS_WIN:
        extra += ["--collect-all", "webview", "--hidden-import", "pystray._win32", "--exclude-module", "PySide6"]
    elif IS_MAC:
        extra += ["--collect-all", "webview", "--exclude-module", "PySide6", "--exclude-module", "PIL"]
    else:
        extra += ["--exclude-module", "webview", "--exclude-module", "gi", "--exclude-module", "PIL"]
    window = pyinstaller(WINDOW, PACKAGING / "viewer_launcher.py", extra)
    if not (IS_WIN or IS_MAC):
        prune_qt(window)
    return window


QT_PLUGIN_DENY = {"qmltooling", "sqldrivers", "sceneparsers", "renderers", "geometryloaders", "assetimporters",
                  "multimedia", "position", "sensors", "texttospeech", "canbus", "designer", "webview",
                  "networkinformation", "printsupport", "renderplugins", "qmllint", "scxmldatamodel"}


def _needed_libs(roots: list[Path], search: list[Path]) -> set[Path]:
    """Transitive closure of shared libraries (inside `search`) that `roots` link against."""
    env = dict(os.environ, LD_LIBRARY_PATH=os.pathsep.join(str(p) for p in search))
    seen: set[Path] = set()
    todo = list(roots)
    inside = [p.resolve() for p in search]
    while todo:
        item = todo.pop()
        out = subprocess.run(["ldd", str(item)], capture_output=True, text=True, env=env).stdout
        for line in out.splitlines():
            # "libX.so => /some path (maybe with brackets)/libX.so (0x00007f...)"
            m = re.search(r"=>\s*(.+?)\s+\(0x[0-9a-fA-F]+\)\s*$", line)
            if not m:
                continue
            target = m.group(1)
            path = Path(target).resolve()
            if any(path.is_relative_to(d) for d in inside) and path not in seen:
                seen.add(path)
                todo.append(path)
    return seen


def prune_qt(window: Path) -> None:
    """Qt WebEngine's PyInstaller hook collects the whole QML/Quick3D stack and every translation;
    the window only needs Widgets + WebEngine. Keep what is actually linked, drop the rest."""
    internal = window / "_internal"
    qt = internal / "PySide6" / "Qt"
    shutil.rmtree(qt / "qml", ignore_errors=True)
    for plugin_dir in (qt / "plugins").iterdir():
        if plugin_dir.name in QT_PLUGIN_DENY or (plugin_dir.name == "platformthemes"):
            shutil.rmtree(plugin_dir, ignore_errors=True)   # gtk3 theme plugin would bundle the host's GTK
    for qm in (qt / "translations").glob("*.qm"):
        qm.unlink()
    for pak in (qt / "translations" / "qtwebengine_locales").glob("*.pak"):
        if pak.name != "en-US.pak":
            pak.unlink()
    roots = [window / WINDOW, *(qt / "libexec").glob("*"), *(qt / "plugins").rglob("*.so"),
             *internal.glob("*.so"), *(internal / "PySide6").glob("*.so"), *internal.rglob("*.cpython-*.so")]
    keep = _needed_libs(roots, [qt / "lib", internal])
    removed = 0
    for folder in (qt / "lib", internal):
        for lib in folder.glob("*.so*"):
            if lib.is_file() and lib.resolve() not in keep and not lib.name.startswith(("libpython", "libQt6WebEngine")):
                if folder == internal and (".cpython-" in lib.name or lib.name.endswith(".abi3.so")):
                    continue
                lib.unlink()
                removed += 1
    print(f"pruned Qt: removed {removed} unused libraries, QML and translations")


def bundle_deno(core: Path) -> None:
    """yt-dlp needs a JavaScript runtime for YouTube's player challenges; ship Deno next to the app."""
    from deno import find_deno_bin
    src = Path(find_deno_bin())
    dest_dir = core / "Contents" / "MacOS" if IS_MAC else core
    shutil.copy2(src, dest_dir / src.name)


def finish_mac_bundle(app: Path, background_only: bool) -> None:
    plist_path = app / "Contents" / "Info.plist"
    info = plistlib.loads(plist_path.read_bytes())
    info.update({"CFBundleName": "ClefTune", "CFBundleDisplayName": "ClefTune",
                 "CFBundleShortVersionString": VERSION, "CFBundleVersion": VERSION,
                 "NSHighResolutionCapable": True, "LSMinimumSystemVersion": "11.0"})
    if background_only:
        info["LSUIElement"] = True     # the core has no window of its own; the window add-on is the Dock app
    plist_path.write_bytes(plistlib.dumps(info))
    identity = os.environ.get("MACOS_SIGN_IDENTITY", "-")   # "-" = ad-hoc (required on Apple Silicon)
    cmd = ["codesign", "--force", "--deep", "--sign", identity]
    if identity != "-":
        cmd += ["--options", "runtime", "--timestamp", "--entitlements", PACKAGING / "macos" / "entitlements.plist"]
    run(cmd + [app])


def package(core: Path, window: Path) -> Path:
    out_dir = DIST / "installers"
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"ClefTune-{VERSION}"
    if IS_WIN:
        out = out_dir / f"{base}-windows-x64-setup.exe"
        iscc = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
        run([iscc, f"/DAppVersion={VERSION}", f"/DCoreDir={core}", f"/DWindowDir={window}", f"/DIconFile={WEB / 'icon.ico'}",
             f"/O{out_dir}", f"/F{out.stem}", PACKAGING / "windows" / "installer.iss"])
    elif IS_MAC:
        out = out_dir / f"{base}-macos-{ARCH}.pkg"
        run(["bash", PACKAGING / "macos" / "make_pkg.sh", core, window, out, VERSION, ARCH])
    else:
        out = out_dir / f"{base}-linux-{ARCH}.run"
        run(["bash", PACKAGING / "linux" / "make_run.sh", core, window, out, VERSION, WEB])
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--keep-build", action="store_true", help="keep build/ (PyInstaller output) afterwards")
    args = parser.parse_args()

    sys.path.insert(0, str(PACKAGING))
    import make_icons                      # every icon comes from assets/clef.png
    make_icons.main()
    core, window = build_core(), build_window()
    bundle_deno(core)
    if IS_MAC:
        finish_mac_bundle(core, background_only=True)
        finish_mac_bundle(window, background_only=False)
    out = package(core, window)
    if not args.keep_build:
        shutil.rmtree(BUILD, ignore_errors=True)
    size = out.stat().st_size / 1e6
    print(f"\nInstaller: {out} ({size:.0f} MB)")


if __name__ == "__main__":
    main()
