"""Easy sign-in: turn YouTube cookies (from our login window or an installed browser) into the
request headers ytmusicapi expects. Cookies only ever travel over the loopback connection."""

from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
LOGIN_URL = ("https://accounts.google.com/ServiceLogin?ltmpl=music&service=youtube&passive=true"
             "&continue=https%3A%2F%2Fmusic.youtube.com%2F")
AUTH_COOKIES = ("SAPISID", "__Secure-3PAPISID")

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
    found = []
    for browser_id, (label, paths) in BROWSERS.items():
        for rel in paths.get(_os_key(), []):
            path = Path(os.path.expandvars(rel)) if "%" in rel else Path.home() / rel
            if path.exists():
                found.append({"id": browser_id, "label": label})
                break
    return found


def has_login(cookies: dict) -> bool:
    return any(name in cookies for name in AUTH_COOKIES)


def headers_from_cookies(cookies: dict, user_agent: str | None = None) -> str:
    if not has_login(cookies):
        raise ValueError("No YouTube login found. Sign in to music.youtube.com first.")
    cookie = "; ".join(f"{k}={v}" for k, v in cookies.items())
    return "\n".join([
        f"cookie: {cookie}",
        f"user-agent: {user_agent or DEFAULT_UA}",
        "x-goog-authuser: 0",
        "origin: https://music.youtube.com",
        "x-origin: https://music.youtube.com",
        "accept: */*",
        "accept-language: en-US,en;q=0.9",
        "content-type: application/json",
    ])


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


def cookies_from_browser(browser_id: str) -> dict:
    if browser_id not in BROWSERS:
        raise ValueError("Unsupported browser")
    from yt_dlp.cookies import extract_cookies_from_browser
    label = BROWSERS[browser_id][0]
    try:
        jar = extract_cookies_from_browser(browser_id, logger=_QuietLogger())
    except Exception as exc:
        hint = " Close the browser and try again, or use \"Sign in with Google\"." if sys.platform.startswith("win") else ""
        raise ValueError(f"Couldn't read {label}'s cookies ({exc}).{hint}") from None
    cookies = {c.name: c.value for c in jar if c.domain.lstrip(".").endswith("youtube.com") and c.value}
    if not has_login(cookies):
        raise ValueError(f"You're not signed in to YouTube in {label}. Open music.youtube.com there, sign in, "
                         f"then try again.")
    return cookies
