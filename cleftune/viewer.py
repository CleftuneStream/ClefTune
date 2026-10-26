"""Window add-on: shows the ClefTune UI in its own native window.

Runs as a separate process (and, in installer builds, a separate optional component) so the
core app works without it. Linux uses Qt WebEngine (fully bundled, no system packages);
Windows and macOS use pywebview on the OS's own engine (WebView2 / WKWebView).

    ClefTuneWindow --url http://127.0.0.1:PORT/ --token TOKEN          the app window
    ClefTuneWindow --login --url ... --token ...                       Google sign-in window

Closing the window hides it (music keeps playing in the app); a tray icon, launching the app
again, or the in-app Quit bring it back or shut everything down.
Exit code 0 = closed normally; anything else = the window couldn't be shown.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

from .auth import LOGIN_URL, has_login
from .config import data_dir

TITLE = "ClefTune"
CHROME_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
SAFARI_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
             "Version/18.0 Safari/605.1.15")
log = logging.getLogger("cleftune.viewer")


def _resource(name: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    for candidate in (base / "cleftune" / "web" / name, Path(__file__).resolve().parent / "web" / name):
        if candidate.is_file():
            return str(candidate)
    return ""


class AppLink:
    """Talks to the running app over its loopback API."""

    def __init__(self, url: str, token: str):
        self.base = url.rstrip("/")
        self.token = token

    def call(self, name: str, **params):
        req = urllib.request.Request(f"{self.base}/api/call/{name}", data=json.dumps(params).encode(),
                                     headers={"X-Token": self.token, "Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp).get("result")

    def call_async(self, name: str, **params) -> None:
        threading.Thread(target=lambda: self._quiet(name, **params), daemon=True).start()

    def _quiet(self, name, **params):
        try:
            self.call(name, **params)
        except Exception as exc:
            log.warning("%s failed: %s", name, exc)

    def keep_in_background(self) -> bool:
        try:
            return bool(self.call("settings").get("close_to_background", True))
        except Exception:
            return True

    def watch(self, on_command, on_gone) -> None:
        """Follow the app's event stream; forward 'window' commands; notice when the app quits."""
        failures = 0
        while True:
            try:
                req = urllib.request.Request(f"{self.base}/api/events?token={self.token}")
                with urllib.request.urlopen(req, timeout=40) as resp:
                    failures = 0
                    event = None
                    for raw in resp:
                        line = raw.decode("utf-8", "replace").rstrip("\r\n")
                        if line.startswith("event:"):
                            event = line[6:].strip()
                        elif line.startswith("data:") and event == "window":
                            on_command(json.loads(line[5:]))
            except Exception as exc:
                log.debug("event stream ended: %s", exc)
            failures += 1
            if failures >= 3:
                on_gone()
                return
            time.sleep(1)


def _notice_file() -> Path:
    return data_dir() / "window" / "background-notice-shown"


BACKGROUND_NOTICE = ("ClefTune keeps playing in the background.\n\n"
                     "Open it again from the app menu or the tray icon. To stop the music completely, "
                     "choose Quit (in the sidebar or the tray menu).")


# ---------------------------------------------------------------------------------------- Qt
def _userns_blocked() -> bool:
    """Chromium's sandbox needs unprivileged user namespaces; Ubuntu 23.10+ (AppArmor) and some
    hardened kernels block them, and Qt WebEngine then refuses to start."""
    checks = {"/proc/sys/kernel/apparmor_restrict_unprivileged_userns": "1",
              "/proc/sys/kernel/unprivileged_userns_clone": "0"}
    for path, blocked in checks.items():
        try:
            if Path(path).read_text().strip() == blocked:
                return True
        except OSError:
            pass
    return False


def _qt_app():
    if _userns_blocked() or os.environ.get("CLEFTUNE_NO_SANDBOX"):
        # the main page is the app's own local UI (strict CSP), so running without the sandbox is acceptable
        os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv[:1])
    # the internal name decides where Qt WebEngine keeps its files: inside the app's own data folder
    app.setApplicationName("cleftune")
    app.setApplicationDisplayName(TITLE)
    app.setDesktopFileName("cleftune")
    if _resource("icon.png"):
        app.setWindowIcon(QIcon(_resource("icon.png")))
    return app


def run_qt(link: AppLink, url: str, storage: Path) -> int:
    from PySide6.QtCore import QObject, QUrl, Signal
    from PySide6.QtGui import QAction
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

    app = _qt_app()
    app.setQuitOnLastWindowClosed(False)
    profile = QWebEngineProfile("cleftune", app)
    profile.setPersistentStoragePath(str(storage / "storage"))
    profile.setCachePath(str(storage / "cache"))
    state = {"quitting": False}

    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(app.windowIcon(), app)
        tray.setToolTip(TITLE)

    class Window(QWebEngineView):
        def closeEvent(self, event):
            if state["quitting"]:
                event.accept()
                return
            event.ignore()
            if not link.keep_in_background():
                link.call_async("quit")
                return
            self.hide()
            if not _notice_file().exists():
                _notice_file().write_text("1")
                if tray:
                    tray.showMessage(TITLE, BACKGROUND_NOTICE.split("\n")[0])
                else:
                    box = QMessageBox(QMessageBox.Icon.Information, TITLE, BACKGROUND_NOTICE)
                    box.addButton("Keep playing", QMessageBox.ButtonRole.AcceptRole)
                    quit_button = box.addButton("Quit ClefTune", QMessageBox.ButtonRole.DestructiveRole)
                    box.exec()
                    if box.clickedButton() is quit_button:
                        link.call_async("quit")

    view = Window()
    page = QWebEnginePage(profile, view)
    page.settings().setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
    view.setPage(page)
    page.loadFinished.connect(lambda ok: log.info("page loaded: %s", "ok" if ok else "FAILED"))
    view.setWindowTitle(TITLE)
    view.resize(1280, 820)
    view.setMinimumSize(940, 600)
    view.load(QUrl(url))
    view.show()

    def show_window():
        view.showNormal()
        view.raise_()
        view.activateWindow()

    def quit_all():
        state["quitting"] = True
        app.quit()

    if tray:
        menu = QMenu()
        for label, action in (("Show ClefTune", show_window), ("Play / Pause", lambda: link.call_async("toggle")),
                              ("Next song", lambda: link.call_async("next")), (None, None),
                              ("Quit", lambda: link.call_async("quit"))):
            if label is None:
                menu.addSeparator()
                continue
            item = QAction(label, menu)
            item.triggered.connect(action)
            menu.addAction(item)
        tray.setContextMenu(menu)
        tray.activated.connect(lambda reason: show_window()
                               if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        tray.show()

    class Bridge(QObject):
        command = Signal(dict)
        gone = Signal()

    bridge = Bridge()
    bridge.command.connect(lambda cmd: show_window() if cmd.get("cmd") == "raise"
                           else quit_all() if cmd.get("cmd") == "close" else None)
    bridge.gone.connect(quit_all)
    threading.Thread(target=link.watch, args=(bridge.command.emit, bridge.gone.emit), daemon=True).start()

    def cleanup():
        view.setPage(None)
        page.deleteLater()   # pages must go before their profile
    app.aboutToQuit.connect(cleanup)
    return app.exec()


def run_qt_login(link: AppLink) -> int:
    from PySide6.QtCore import QObject, QTimer, QUrl, Signal
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QMessageBox

    app = _qt_app()
    profile = QWebEngineProfile(app)                 # private: nothing of the Google session is kept on disk
    profile.setHttpUserAgent(CHROME_UA)
    cookies: dict = {}
    profile.cookieStore().cookieAdded.connect(
        lambda c: c.domain().lstrip(".").endswith("youtube.com") and
        cookies.__setitem__(bytes(c.name()).decode(), bytes(c.value()).decode()))
    view = QWebEngineView()
    page = QWebEnginePage(profile, view)
    view.setPage(page)
    page.urlChanged.connect(lambda u: log.info("sign-in page: %s%s", u.host(), u.path()))
    view.setWindowTitle("Sign in to YouTube Music – ClefTune")
    view.resize(520, 760)
    view.load(QUrl(LOGIN_URL))
    view.show()

    class Bridge(QObject):
        done = Signal(str)

    bridge = Bridge()
    state = {"sent": False}

    def finish(error: str) -> None:
        if error:
            QMessageBox.warning(view, TITLE, error)
            state["sent"] = False
            return
        app.quit()
    bridge.done.connect(finish)

    def check() -> None:
        if state["sent"] or "music.youtube.com" not in page.url().host() or not has_login(cookies):
            return
        state["sent"] = True

        def send():
            try:
                link.call("login_cookies", cookies=dict(cookies), user_agent=CHROME_UA)
                bridge.done.emit("")
            except Exception as exc:
                bridge.done.emit(f"Sign-in didn't work: {exc}")
        threading.Thread(target=send, daemon=True).start()

    timer = QTimer()
    timer.timeout.connect(check)
    timer.start(700)

    def cleanup():
        view.setPage(None)
        page.deleteLater()
    app.aboutToQuit.connect(cleanup)
    return app.exec()


# ----------------------------------------------------------------------------------- pywebview
def _start_windows_tray(link: AppLink, show) -> object | None:
    if not sys.platform.startswith("win"):
        return None          # macOS keeps the app in the Dock instead
    try:
        import pystray
        from PIL import Image
    except ImportError:
        return None
    item = pystray.MenuItem
    icon = pystray.Icon("cleftune", Image.open(_resource("icon.png")), TITLE, pystray.Menu(
        item("Show ClefTune", lambda: show(), default=True),
        item("Play / Pause", lambda: link.call_async("toggle")),
        item("Next song", lambda: link.call_async("next")),
        pystray.Menu.SEPARATOR,
        item("Quit", lambda: link.call_async("quit"))))
    threading.Thread(target=icon.run, daemon=True).start()
    return icon


def run_pywebview(link: AppLink, url: str, storage: Path, debug: bool) -> int:
    import webview

    window = webview.create_window(TITLE, url, width=1280, height=820, min_size=(940, 600),
                                   background_color="#0e0e12", text_select=False)
    state = {"quitting": False, "tray": None}

    def show():
        try:
            window.show()
            window.restore()
            window.on_top = True
            window.on_top = False
        except Exception as exc:
            log.warning("show failed: %s", exc)

    def quit_all():
        state["quitting"] = True
        if state["tray"]:
            state["tray"].stop()
        try:
            window.destroy()
        except Exception:
            pass

    def on_closing():
        if state["quitting"]:
            return True
        if not link.keep_in_background():
            link.call_async("quit")
            return False
        window.hide()
        if not _notice_file().exists():
            _notice_file().write_text("1")
            if state["tray"]:
                state["tray"].notify(BACKGROUND_NOTICE.split("\n")[0], TITLE)
        return False          # cancel the close: keep playing in the background

    window.events.closing += on_closing

    def background():
        state["tray"] = _start_windows_tray(link, show)
        link.watch(lambda cmd: show() if cmd.get("cmd") == "raise" else quit_all() if cmd.get("cmd") == "close" else None,
                   quit_all)

    gui = "edgechromium" if sys.platform.startswith("win") else ("cocoa" if sys.platform == "darwin" else None)
    webview.start(background, gui=gui, private_mode=False, storage_path=str(storage), icon=_resource("icon.png") or None,
                  debug=debug)
    return 0


def run_pywebview_login(link: AppLink) -> int:
    import webview

    window = webview.create_window("Sign in to YouTube Music – ClefTune", LOGIN_URL, width=520, height=760)

    def poll():
        while True:
            time.sleep(1)
            try:
                if "music.youtube.com" not in (window.get_current_url() or ""):
                    continue
                cookies = {}
                for jar in window.get_cookies() or []:
                    for name, morsel in jar.items():
                        if (morsel["domain"] or "").lstrip(".").endswith("youtube.com"):
                            cookies[name] = morsel.value
                if has_login(cookies):
                    link.call("login_cookies", cookies=cookies, user_agent="")
                    window.destroy()
                    return
            except Exception as exc:
                log.warning("sign-in check failed: %s", exc)

    ua = SAFARI_UA if sys.platform == "darwin" else None
    gui = "edgechromium" if sys.platform.startswith("win") else ("cocoa" if sys.platform == "darwin" else None)
    webview.start(poll, gui=gui, private_mode=True, user_agent=ua)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ClefTuneWindow")
    parser.add_argument("--url", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--login", action="store_true", help="show the Google sign-in window")
    parser.add_argument("--backend", choices=["auto", "qt", "pywebview"], default="auto")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    storage = data_dir() / "window"
    storage.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        handlers=[logging.FileHandler(data_dir() / "window.log", encoding="utf-8")],
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not args.url.startswith(("http://127.0.0.1:", "http://localhost:")):
        log.error("refusing to open a non-local URL")
        return 2
    link = AppLink(args.url, args.token)

    if args.login:
        backends = {"qt": lambda: run_qt_login(link), "pywebview": lambda: run_pywebview_login(link)}
    else:
        backends = {"qt": lambda: run_qt(link, args.url, storage),
                    "pywebview": lambda: run_pywebview(link, args.url, storage, args.debug)}
    order = [args.backend] if args.backend != "auto" else (
        ["qt", "pywebview"] if sys.platform.startswith("linux") else ["pywebview"])
    for name in order:
        try:
            log.info("starting %s %s", name, "sign-in window" if args.login else "window")
            return backends[name]()
        except ImportError as exc:
            log.info("%s backend unavailable: %s", name, exc)
        except Exception:
            log.exception("%s window failed", name)
    return 3


if __name__ == "__main__":
    sys.exit(main())
