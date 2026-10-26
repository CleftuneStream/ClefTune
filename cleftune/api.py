"""RPC methods exposed to the UI as POST /api/call/<name> (JSON body = keyword arguments)."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import threading

import yt_dlp
import ytmusicapi

from . import APP_NAME, __version__
from .config import FROZEN, IS_WINDOWS


def _track(t: dict) -> dict:
    if not isinstance(t, dict) or not t.get("videoId"):
        raise ValueError("A track with a videoId is required")
    return t


def _tracks(tracks) -> list[dict]:
    if not isinstance(tracks, list):
        raise ValueError("tracks must be a list")
    return [_track(t) for t in tracks]


class Api:
    def __init__(self, app):
        self.app = app

    @property
    def player(self):
        return self.app.player

    # -- browse -----------------------------------------------------------
    def rpc_home(self):
        return self.app.ytm.home()

    def rpc_explore(self):
        return self.app.ytm.explore()

    def rpc_mood(self, params: str, title: str = ""):
        return {"title": title, "items": self.app.ytm.mood_playlists(params)}

    def rpc_search(self, query: str, kind: str = ""):
        return self.app.ytm.search(query, kind or None)

    def rpc_suggestions(self, query: str):
        return self.app.ytm.suggestions(query)

    def rpc_album(self, id: str):
        return self._with_saved(self.app.ytm.album(id))

    def rpc_artist(self, id: str):
        return self._with_saved(self.app.ytm.artist(id))

    def rpc_playlist(self, id: str, title: str = ""):
        if id.isdigit():
            data = self.app.library.playlist(int(id))
            if not data:
                raise ValueError("Playlist not found")
            return data
        if id.startswith("RD") and not id.startswith("RDCLAK"):
            # radio mixes only exist as watch playlists
            data = self.app.ytm.up_next(playlist_id=id)
            tracks = data["tracks"]
            return {"type": "playlist", "id": id, "title": title or "Mix", "subtitle": f"Mix • {len(tracks)} songs",
                    "description": "", "thumbnail": tracks[0]["thumbnail"] if tracks else None, "tracks": tracks,
                    "saved": self.app.library.is_saved("playlist", id)}
        return self._with_saved(self.app.ytm.playlist(id))

    def _with_saved(self, page: dict) -> dict:
        return page | {"saved": self.app.library.is_saved(page["type"], page["id"])}

    def rpc_lyrics(self, track: dict):
        track = _track(track)
        return self.app.lyrics.get(track) | {"offset": self.app.library.lyrics_offset(track["videoId"])}

    def rpc_lyrics_offset(self, videoId: str, offset: float):
        offset = max(-10.0, min(10.0, round(float(offset), 2)))
        self.app.library.set_lyrics_offset(videoId, offset)
        return offset

    def rpc_prefetch(self, videoIds: list):
        self.player.prefetch([v for v in videoIds if isinstance(v, str)])

    # -- song cache -------------------------------------------------------
    def rpc_cache(self):
        return {"items": self.app.library.cached_tracks(), **self.app.song_cache.stats()}

    def rpc_cache_clear(self):
        self.app.song_cache.clear()

    # -- playback ---------------------------------------------------------
    def rpc_state(self):
        return {"state": self.player.state(), "queue": self.player.queue_payload()}

    def rpc_play_tracks(self, tracks: list, index: int = 0, title: str = "", shuffle: bool = False):
        self.player.play_tracks(_tracks(tracks), index=index, title=title, shuffle=shuffle)

    def rpc_play_radio(self, track: dict):
        self.player.play_radio(_track(track))

    def rpc_play_playlist_radio(self, playlist_id: str, title: str = ""):
        threading.Thread(target=self._playlist_radio, args=(playlist_id, title), daemon=True).start()

    def _playlist_radio(self, playlist_id, title):
        try:
            self.player.play_playlist_radio(playlist_id, title)
        except Exception as exc:
            self.app.bus.emit("toast", {"message": f"Couldn't start the mix: {exc}", "kind": "error"})

    def rpc_add_next(self, tracks: list):
        self.player.add_next(_tracks(tracks))

    def rpc_add_queue(self, tracks: list):
        self.player.add_to_queue(_tracks(tracks))

    def rpc_queue_remove(self, index: int):
        self.player.remove(int(index))

    def rpc_queue_move(self, src: int, dst: int):
        self.player.move(int(src), int(dst))

    def rpc_queue_jump(self, index: int):
        self.player.jump(int(index))

    def rpc_queue_clear(self):
        self.player.clear_queue()

    def rpc_toggle(self):
        self.player.toggle()

    def rpc_next(self):
        self.player.next()

    def rpc_previous(self):
        self.player.previous()

    def rpc_seek(self, pos: float):
        self.player.seek(float(pos))

    def rpc_volume(self, volume: int):
        self.player.set_volume(int(volume))

    def rpc_shuffle(self, enabled: bool):
        self.player.set_shuffle(bool(enabled))

    def rpc_repeat(self, mode: str):
        self.player.set_repeat(mode)

    def rpc_sleep(self, minutes: float):
        self.player.set_sleep(float(minutes))

    def rpc_engine_report(self, event: str, pos: float = 0, duration: float = 0, paused: bool = True,
                          message: str = "", src: str = ""):
        engine = self.player.engine
        if getattr(engine, "name", "") == "web":
            engine.report(event, pos=pos, duration=duration, paused=paused, message=message, src=src)

    # -- library ----------------------------------------------------------
    def rpc_like(self, track: dict, liked: bool):
        self.player.set_liked(_track(track), bool(liked))
        return liked

    def rpc_liked_ids(self):
        return self.app.library.liked_ids()

    def rpc_library(self):
        lib = self.app.library
        return {"liked": lib.liked(), "playlists": lib.playlists(), "saved": lib.saved(),
                "account": self.app.ytm.authenticated}

    def rpc_history(self):
        return self.app.library.history()

    def rpc_history_clear(self):
        self.app.library.clear_history()

    def rpc_stats(self, days: int = 30):
        return self.app.library.stats(int(days))

    def rpc_playlists(self):
        return self.app.library.playlists()

    def rpc_playlist_create(self, name: str, tracks: list | None = None):
        return str(self.app.library.create_playlist(name, _tracks(tracks or [])))

    def rpc_playlist_rename(self, id: str, name: str):
        self.app.library.rename_playlist(int(id), name)

    def rpc_playlist_delete(self, id: str):
        self.app.library.delete_playlist(int(id))

    def rpc_playlist_add(self, id: str, tracks: list):
        return self.app.library.add_to_playlist(int(id), _tracks(tracks))

    def rpc_playlist_remove(self, id: str, index: int):
        self.app.library.remove_from_playlist(int(id), int(index))

    def rpc_playlist_move(self, id: str, src: int, dst: int):
        self.app.library.move_in_playlist(int(id), int(src), int(dst))

    def rpc_save(self, item: dict, saved: bool):
        if item.get("type") not in ("album", "artist", "playlist") or not item.get("id"):
            raise ValueError("Only albums, artists and playlists can be saved")
        if saved:
            self.app.library.save(item)
        else:
            self.app.library.unsave(item["type"], item["id"])
        return saved

    # -- account ----------------------------------------------------------
    def rpc_account(self):
        if not self.app.ytm.authenticated:
            return {"signedIn": False}
        try:
            return {"signedIn": True} | self.app.ytm.account_info()
        except Exception as exc:
            return {"signedIn": True, "name": None, "error": str(exc)}

    def rpc_login(self, headers: str):
        info = self.app.ytm.login(headers)
        self.app.resolver.clear()
        self.app.bus.emit("account", {"signedIn": True})
        return info

    def rpc_login_window(self):
        self.app.start_login_window()

    def rpc_login_cookies(self, cookies: dict, user_agent: str = ""):
        """Called by the sign-in window with the YouTube cookies it captured."""
        from .auth import headers_from_cookies
        try:
            info = self.rpc_login(headers_from_cookies(cookies, user_agent or None))
        except ValueError as exc:
            self.app.bus.emit("toast", {"message": str(exc), "kind": "error"})
            raise
        self.app.bus.emit("toast", {"message": f"Signed in as {info.get('name') or 'your account'}"})
        self.app.raise_window()
        return info

    def rpc_login_browsers(self):
        from .auth import installed_browsers
        return installed_browsers()

    def rpc_login_browser(self, browser: str):
        from .auth import cookies_from_browser, headers_from_cookies
        return self.rpc_login(headers_from_cookies(cookies_from_browser(browser)))

    def rpc_logout(self):
        self.app.ytm.logout()
        self.app.resolver.clear()
        self.app.bus.emit("account", {"signedIn": False})

    def rpc_account_library(self):
        ytm = self.app.ytm
        if not ytm.authenticated:
            raise ValueError("Not signed in")
        return {"liked": ytm.account_liked(), "playlists": ytm.account_playlists()}

    def rpc_account_history(self):
        return self.app.ytm.account_history()

    # -- downloads --------------------------------------------------------
    def rpc_download(self, tracks: list):
        return self.app.downloads.add(_tracks(tracks))

    def rpc_downloads(self):
        return {"items": self.app.library.downloads(), "folder": str(self.app.settings.download_dir()),
                "ffmpeg": bool(self.app.downloads.ffmpeg)}

    def rpc_download_ids(self):
        return self.app.library.download_ids()

    def rpc_download_delete(self, videoId: str):
        self.app.downloads.delete(videoId)

    def rpc_open_downloads(self):
        folder = str(self.app.settings.download_dir(create=True))
        if IS_WINDOWS:
            os.startfile(folder)  # noqa: S606
        elif shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", folder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return folder

    # -- settings & about -------------------------------------------------
    def rpc_settings(self):
        return self.app.settings.all()

    def rpc_settings_set(self, patch: dict):
        before = self.app.settings.all()
        values = self.app.settings.update(patch)
        if {"language", "location"} & patch.keys():
            self.app.ytm.reset()
        if {"audio_quality", "prefer_m4a", "use_account_for_playback"} & patch.keys():
            self.app.resolver.clear()
        if "normalize" in patch and self.player.engine:
            self.player.engine.set_normalize(values["normalize"])
        if {"cache_songs", "cache_enabled"} & patch.keys():
            if not values["cache_enabled"]:
                self.app.song_cache.clear()
            threading.Thread(target=self.app.song_cache.evict, daemon=True).start()
        restart = "engine" in patch and patch["engine"] != before["engine"]
        return {"settings": values, "restartRequired": restart}

    def rpc_about(self):
        from .app import window_install_hint
        runtimes = self.app.resolver.js_runtimes
        return {
            "app": APP_NAME, "version": __version__, "python": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}", "engine": self.player.engine.name,
            "ytdlp": yt_dlp.version.__version__, "ytmusicapi": getattr(ytmusicapi, "__version__", "?"),
            "jsRuntime": next(iter(runtimes), None), "ffmpeg": bool(self.app.downloads.ffmpeg),
            "mpris": self.app.mpris_active, "window": self.app.window_mode,
            "windowAvailable": self.app.window_available, "windowHint": window_install_hint(),
            "installed": FROZEN,
        }

    def rpc_set_ui_mode(self, mode: str):
        return self.app.switch_ui(mode)

    def rpc_engine_status(self):
        from . import engine_update
        return engine_update.status()

    def rpc_engine_update(self):
        from . import engine_update
        return engine_update.update()

    def rpc_engine_reset(self):
        from . import engine_update
        engine_update.reset()
        return {"message": "Restart to go back to the YouTube engine that came with the app."}

    def rpc_clear_cache(self):
        self.app.ytm.reset()
        self.app.resolver.clear()

    def rpc_open_url(self, url: str):
        if not url.startswith(("https://music.youtube.com/", "https://www.youtube.com/", "https://github.com/",
                               "https://lrclib.net/")):
            raise ValueError("URL not allowed")
        import webbrowser
        webbrowser.open(url)

    def rpc_raise_window(self):
        self.app.raise_window()

    def rpc_quit(self):
        threading.Timer(0.2, self.app.quit).start()

    def rpc_ping(self):
        return {"pid": os.getpid(), "python": sys.version.split()[0]}
