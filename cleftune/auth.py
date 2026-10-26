"""Easy sign-in: read the YouTube login from a browser installed on this computer (the default one
first) and turn its cookies into the request headers ytmusicapi expects. Google's own sign-in page
runs in that real browser, so Google never sees an embedded "unsafe" browser. Cookies never leave
this computer."""

from __future__ import annotations

import hashlib
import os
import plistlib
import re
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
LOGIN_URL = ("https://accounts.google.com/ServiceLogin?ltmpl=music&service=youtube&passive=true"
             "&continue=https%3A%2F%2Fmusic.youtube.com%2F")
ORIGIN = "https://music.youtube.com"
AUTH_COOKIES = ("__Secure-3PAPISID", "SAPISID")

BROWSERS = {   # id: (label, profile folders per OS, relative to home / %APPDATA% / %LOCALAPPDATA%)
    "firefox": ("Firefox", {"linux": [".mozilla/firefox", "snap/firefox/common/.mozilla/firefox",
                                      ".var/app/org.mozilla.firefox/.mozilla/firefox"],
                            "win": ["%APPDATA%/Mozilla/Firefox"], "mac": ["Library/Application Support/Firefox"]}),
    "chrome": ("Google Chrome", {"linux": [".config/google-chrome"], "win": ["%LOCALAPPDATA%/Google/Chrome/User Data"],
                                 "mac": ["Library/Application Support/Google/Chrome"]}),
    "edge": ("Microsoft Edge", {"linux": [".config/microsoft-edge"], "win": ["%LOCALAPPDATA%/Microsoft/Edge/User Data"],
                                "mac": ["Library/Application Support/Microsoft Edge"]}),
    "brave": ("Brave", {"linux": [".config/BraveSoftware/Brave-Browser"],
                        "win": ["%LOCALAPPDATA%/BraveSoftware/Brave-Browser/User Data"],
                        "mac": ["Library/Application Support/BraveSoftware/Brave-Browser"]}),
    "chromium": ("Chromium", {"linux": [".config/chromium", "snap/chromium/common/chromium"],
                              "win": ["%LOCALAPPDATA%/Chromium/User Data"], "mac": ["Library/Application Support/Chromium"]}),
    "opera": ("Opera", {"linux": [".config/opera"], "win": ["%APPDATA%/Opera Software/Opera Stable"],
                        "mac": ["Library/Application Support/com.operasoftware.Opera"]}),
    "vivaldi": ("Vivaldi", {"linux": [".config/vivaldi"], "win": ["%LOCALAPPDATA%/Vivaldi/User Data"],
                            "mac": ["Library/Application Support/Vivaldi"]}),
    "safari": ("Safari", {"mac": ["Library/Containers/com.apple.Safari", "Library/Cookies"]}),
}


def _os_key() -> str:
    return "win" if sys.platform.startswith("win") else "mac" if sys.platform == "darwin" else "linux"


def installed_browsers() -> list[dict]:
    """Browsers with a profile on this computer; the default browser comes first."""
    found = []
    default = default_browser()
    for browser_id, (label, paths) in BROWSERS.items():
        for rel in paths.get(_os_key(), []):
            path = Path(os.path.expandvars(rel)) if "%" in rel else Path.home() / rel
            if path.exists():
                found.append({"id": browser_id, "label": label, "default": browser_id == default})
                break
    return sorted(found, key=lambda b: not b["default"])


def has_login(cookies: dict) -> bool:
    return any(name in cookies for name in AUTH_COOKIES)


def sapisid_hash(sapisid: str) -> str:
    """The Authorization value YouTube expects for cookie logins. ytmusicapi recomputes it for every
    request, but only treats a headers file as a browser login when one is present."""
    stamp = str(int(time.time()))
    return f"SAPISIDHASH {stamp}_{hashlib.sha1(f'{stamp} {sapisid} {ORIGIN}'.encode()).hexdigest()}"


def headers_from_cookies(cookies: dict, user_agent: str | None = None) -> str:
    if not has_login(cookies):
        raise ValueError("No YouTube login found. Sign in to music.youtube.com first.")
    cookies = dict(cookies)
    # ytmusicapi signs requests with __Secure-3PAPISID; older logins only carry SAPISID (same value)
    cookies.setdefault("__Secure-3PAPISID", cookies.get("SAPISID", ""))
    cookie = "; ".join(f"{k}={v}" for k, v in cookies.items())
    return "\n".join([
        f"cookie: {cookie}",
        f"user-agent: {user_agent or DEFAULT_UA}",
        f"authorization: {sapisid_hash(cookies['__Secure-3PAPISID'])}",
        "x-goog-authuser: 0",
        f"origin: {ORIGIN}",
        f"x-origin: {ORIGIN}",
        "accept: */*",
        "accept-language: en-US,en;q=0.9",
        "content-type: application/json",
    ])


def complete_headers(headers_raw: str) -> str:
    """Pasted request headers: add the Authorization line when the copy lacks it (Firefox often
    drops it), so ytmusicapi recognises them as a browser login."""
    if re.search(r"^authorization:\s*SAPISIDHASH", headers_raw, re.I | re.M):
        return headers_raw
    match = re.search(r"(?:__Secure-3PAPISID|SAPISID)=([^;\s]+)", headers_raw)
    if not match:
        raise ValueError("The pasted headers have no SAPISID cookie. Copy them from a music.youtube.com "
                         "request while signed in.")
    lines = [ln for ln in headers_raw.splitlines() if not ln.lower().startswith("authorization:")]
    return "\n".join(lines + [f"authorization: {sapisid_hash(match.group(1))}"])


# ------------------------------------------------------------------ default browser
# Desktop file (Linux), ProgId prefix (Windows) or bundle id (macOS) -> our browser id
_LINUX_DEFAULTS = {"firefox": "firefox", "org.mozilla.firefox": "firefox", "google-chrome": "chrome",
                   "com.google.chrome": "chrome", "microsoft-edge": "edge", "com.microsoft.edge": "edge",
                   "brave-browser": "brave", "com.brave.browser": "brave", "chromium": "chromium",
                   "chromium-browser": "chromium", "org.chromium.chromium": "chromium", "opera": "opera",
                   "com.opera.opera": "opera", "vivaldi-stable": "vivaldi", "vivaldi": "vivaldi",
                   "com.vivaldi.vivaldi": "vivaldi"}
_WINDOWS_DEFAULTS = {"firefoxurl": "firefox", "chromehtml": "chrome", "msedgehtm": "edge", "bravehtml": "brave",
                     "chromiumhtm": "chromium", "operastable": "opera", "vivaldihtm": "vivaldi"}
_MAC_DEFAULTS = {"org.mozilla.firefox": "firefox", "com.google.chrome": "chrome", "com.microsoft.edgemac": "edge",
                 "com.brave.browser": "brave", "org.chromium.chromium": "chromium", "com.operasoftware.opera": "opera",
                 "com.vivaldi.vivaldi": "vivaldi", "com.apple.safari": "safari"}


def _default_browser_key() -> str:
    os_key = _os_key()
    try:
        if os_key == "linux":
            out = subprocess.run(["xdg-settings", "get", "default-web-browser"], capture_output=True, text=True,
                                 timeout=5).stdout.strip()
            return out.removesuffix(".desktop").lower()
        if os_key == "win":
            import winreg
            path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                return str(winreg.QueryValueEx(key, "ProgId")[0]).lower()
        plist = Path.home() / "Library/Preferences/com.apple.LaunchServices/com.apple.launchservices.secure.plist"
        for handler in plistlib.loads(plist.read_bytes()).get("LSHandlers", []):
            if handler.get("LSHandlerURLScheme") == "https":
                return str(handler.get("LSHandlerRoleAll", "")).lower()
    except Exception:
        pass
    return ""


def default_browser() -> str | None:
    """Our id for the system's default web browser, if it's one we can read logins from."""
    key, os_key = _default_browser_key(), _os_key()
    if not key:
        return None
    if os_key == "win":
        return next((bid for prefix, bid in _WINDOWS_DEFAULTS.items() if key.startswith(prefix)), None)
    table = _LINUX_DEFAULTS if os_key == "linux" else _MAC_DEFAULTS
    return table.get(key) or next((bid for name, bid in table.items() if name in key), None)


class _QuietLogger:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg, only_once=False): pass
    def error(self, msg): pass

    class ProgressBar:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def print(self, *a): pass

    def progress_bar(self):
        return self.ProgressBar()


class NotSignedIn(ValueError):
    """The browser was read fine, it just has no YouTube login (yet)."""


def cookies_from_browser(browser_id: str) -> dict:
    if browser_id not in BROWSERS:
        raise ValueError("Unsupported browser")
    from yt_dlp.cookies import extract_cookies_from_browser
    label = BROWSERS[browser_id][0]
    try:
        jar = extract_cookies_from_browser(browser_id, logger=_QuietLogger())
    except Exception as exc:
        hint = " Close the browser completely and try again." if sys.platform.startswith("win") else ""
        raise ValueError(f"Couldn't read {label}'s cookies ({exc}).{hint}") from None
    cookies = {c.name: c.value for c in jar if c.domain.lstrip(".").endswith("youtube.com") and c.value}
    if not has_login(cookies):
        raise NotSignedIn(f"You're not signed in to YouTube in {label}. Sign in at music.youtube.com there, "
                          f"then try again.")
    return cookies
