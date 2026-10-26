"""YouTube Music data access (home, search, pages, up next, account) via ytmusicapi."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from ytmusicapi import YTMusic
import ytmusicapi

from . import models
from .config import Settings, data_dir


class TTLCache:
    def __init__(self, ttl: float, max_items: int = 256):
        self.ttl, self.max_items = ttl, max_items
        self._items: dict = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            hit = self._items.get(key)
            if hit and hit[0] > time.monotonic():
                return hit[1]
            return None

    def put(self, key, value):
        with self._lock:
            if len(self._items) >= self.max_items:
                oldest = min(self._items, key=lambda k: self._items[k][0])
                del self._items[oldest]
            self._items[key] = (time.monotonic() + self.ttl, value)

    def clear(self):
        with self._lock:
            self._items.clear()


class YTM:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.auth_path: Path = data_dir() / "browser_auth.json"
        self._lock = threading.Lock()
        self._client: YTMusic | None = None
        self._cache = TTLCache(ttl=300)

    # -- client lifecycle -------------------------------------------------
    @property
    def client(self) -> YTMusic:
        with self._lock:
            if self._client is None:
                self._client = self._build()
            return self._client

    def _build(self) -> YTMusic:
        kwargs = {"language": self.settings.get("language") or "en"}
        location = self.settings.get("location")
        if location:
            kwargs["location"] = location.upper()
        auth = str(self.auth_path) if self.auth_path.exists() else None
        if auth:
            self._repair_auth_file()
        try:
            return YTMusic(auth, **kwargs)
        except Exception:
            kwargs.pop("location", None)
            kwargs["language"] = "en"
            return YTMusic(auth, **kwargs)

    def reset(self) -> None:
        with self._lock:
            self._client = None
        self._cache.clear()

    @property
    def authenticated(self) -> bool:
        return self.auth_path.exists()

    def _repair_auth_file(self) -> None:
        """Logins saved by older versions lack the Authorization header, which makes ytmusicapi 1.12+
        mistake them for OAuth tokens ("oauth_credentials not provided")."""
        from .auth import sapisid_hash
        try:
            headers = json.loads(self.auth_path.read_text(encoding="utf-8"))
            if any(k.lower() == "authorization" for k in headers):
                return
            cookie = next(v for k, v in headers.items() if k.lower() == "cookie")
            sapisid = next(p.split("=", 1)[1] for p in (x.strip() for x in cookie.split(";"))
                           if p.startswith(("__Secure-3PAPISID=", "SAPISID=")))
            if "__Secure-3PAPISID=" not in cookie:
                headers["cookie"] = f"{cookie}; __Secure-3PAPISID={sapisid}"
            headers["authorization"] = sapisid_hash(sapisid)
            self.auth_path.write_text(json.dumps(headers, ensure_ascii=True, indent=4), encoding="utf-8")
        except (OSError, ValueError, StopIteration):
            pass

    def login(self, headers_raw: str) -> dict:
        from .auth import complete_headers
        if "cookie" not in headers_raw.lower():
            raise ValueError("The pasted headers have no Cookie line. Copy the request headers of a "
                             "music.youtube.com 'browse' request while signed in.")
        ytmusicapi.setup(filepath=str(self.auth_path), headers_raw=complete_headers(headers_raw))
        self.reset()
        try:
            return self.account_info()
        except Exception as exc:
            self.logout()
            raise ValueError(f"Sign-in failed, the headers may be expired or incomplete ({exc}).") from exc

    def logout(self) -> None:
        self.auth_path.unlink(missing_ok=True)
        self.reset()

    def visitor_data(self) -> str | None:
        """YouTube visitor ID; lets stream lookups skip downloading the watch page."""
        hit = self._cache.get("visitor")
        if hit:
            return hit
        value = next((v for k, v in self.client.headers.items() if k.lower() == "x-goog-visitor-id"), None)
        if value:
            self._cache.put("visitor", value)
        return value

    def cookie_header(self) -> str | None:
        try:
            headers = json.loads(self.auth_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return next((v for k, v in headers.items() if k.lower() == "cookie"), None)

    def _cached(self, key, fn):
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        value = fn()
        self._cache.put(key, value)
        return value

    # -- browse -----------------------------------------------------------
    def home(self) -> list[dict]:
        def load():
            sections = self.client.get_home(limit=12)
            return [s for s in (models.shelf(sec.get("title", ""), sec.get("contents")) for sec in sections) if s]
        return self._cached("home", load)

    def explore(self) -> dict:
        def load():
            out = {"shelves": [], "moods": []}
            try:
                data = self.client.get_explore()
            except Exception:
                data = {}
            for key, title in (("new_releases", "New releases"), ("top_songs", "Top songs"),
                               ("trending", "Trending"), ("new_videos", "New music videos")):
                section = data.get(key)
                items = section.get("items") if isinstance(section, dict) else section
                shelf = models.shelf(title, items)
                if shelf:
                    out["shelves"].append(shelf)
            try:
                charts = self.client.get_charts(self.settings.get("location").upper() or "ZZ")
            except Exception:
                charts = {}
            for key, title in (("videos", "Charts"), ("artists", "Top artists")):
                shelf = models.shelf(title, charts.get(key))
                if shelf:
                    out["shelves"].insert(0 if key == "videos" else len(out["shelves"]), shelf)
            for group, entries in self.client.get_mood_categories().items():
                out["moods"].append({"title": group, "items": [{"title": e["title"], "params": e["params"]}
                                                               for e in entries]})
            return out
        return self._cached("explore", load)

    def mood_playlists(self, params: str) -> list[dict]:
        return self._cached(("mood", params), lambda: [
            x for x in (models.from_shelf(p) for p in self.client.get_mood_playlists(params)) if x])

    def search(self, query: str, kind: str | None = None) -> dict:
        filters = {"songs": "songs", "videos": "videos", "albums": "albums",
                   "artists": "artists", "playlists": "playlists"}
        results = self.client.search(query, filter=filters.get(kind or ""), limit=40)
        top, songs, cards, seen = None, [], [], set()
        for raw in results:
            item = models.from_search(raw)
            if not item:
                continue
            key = (item["type"], item.get("videoId") or item.get("id"))
            if key in seen:            # later result pages repeat items
                continue
            seen.add(key)
            if raw.get("category") == "Top result" and top is None:
                top = item
                continue
            (songs if item["type"] == "song" else cards).append(item)
        # YouTube Music's own order mixes in remixes, covers and live cuts; put the hits first
        return {"top": top, "songs": models.rank_by_popularity(songs, query), "cards": cards}

    def suggestions(self, query: str) -> list[str]:
        if not query.strip():
            return []
        try:
            return [s if isinstance(s, str) else s.get("text", "") for s in
                    self.client.get_search_suggestions(query)][:8]
        except Exception:
            return []

    def album(self, browse_id: str) -> dict:
        def load():
            data = self.client.get_album(browse_id)
            thumb = models.best_thumbnail(data.get("thumbnails"))
            album_ref = {"name": data.get("title"), "id": browse_id}
            artists = [{"name": a.get("name"), "id": a.get("id")} for a in data.get("artists") or []]
            return {
                "type": "album", "id": browse_id, "title": data.get("title"),
                "subtitle": " • ".join(str(x) for x in (data.get("type"), data.get("year"),
                                                          data.get("trackCount") and f"{data['trackCount']} songs",
                                                          data.get("duration")) if x),
                "artists": artists, "thumbnail": thumb, "description": data.get("description") or "",
                "playlistId": data.get("audioPlaylistId"),
                "tracks": models.tracks(data.get("tracks"), fallback_thumbnail=thumb, fallback_album=album_ref),
                "related": [x for x in (models.from_shelf(o) for o in data.get("other_versions") or []) if x],
            }
        return self._cached(("album", browse_id), load)

    def artist(self, channel_id: str) -> dict:
        def load():
            data = self.client.get_artist(channel_id)
            songs = data.get("songs") or {}
            shelves = []
            for key, title in (("albums", "Albums"), ("singles", "Singles & EPs"),
                               ("videos", "Videos"), ("related", "Fans might also like")):
                shelf = models.shelf(title, (data.get(key) or {}).get("results"))
                if shelf:
                    shelves.append(shelf)
            return {
                "type": "artist", "id": channel_id, "title": data.get("name"),
                "subtitle": " • ".join(x for x in (data.get("subscribers") and f"{data['subscribers']} subscribers",
                                                   data.get("monthlyListeners") and
                                                   f"{data['monthlyListeners']} monthly listeners") if x),
                "description": data.get("description") or "",
                "thumbnail": models.best_thumbnail(data.get("thumbnails"), 720),
                "radioId": data.get("radioId"), "shuffleId": data.get("shuffleId"),
                "songs": models.tracks(songs.get("results")),
                "songsPlaylistId": songs.get("browseId"),
                "shelves": shelves,
            }
        return self._cached(("artist", channel_id), load)

    def playlist(self, playlist_id: str, limit: int | None = 300) -> dict:
        def load():
            data = self.client.get_playlist(playlist_id, limit=limit)
            author = data.get("author")
            author_name = author.get("name") if isinstance(author, dict) else author
            return {
                "type": "playlist", "id": playlist_id, "title": data.get("title"),
                "subtitle": " • ".join(str(x) for x in (author_name, data.get("year"),
                                                          data.get("trackCount") and f"{data['trackCount']} songs",
                                                          data.get("duration")) if x),
                "description": data.get("description") or "",
                "thumbnail": models.best_thumbnail(data.get("thumbnails")),
                "tracks": models.tracks(data.get("tracks")),
                "owned": bool(data.get("owned")),
            }
        return self._cached(("playlist", playlist_id, limit), load)

    def up_next(self, video_id: str | None = None, playlist_id: str | None = None, limit: int = 50) -> dict:
        data = self.client.get_watch_playlist(videoId=video_id, playlistId=playlist_id, limit=limit)
        return {"tracks": models.tracks(data.get("tracks")), "lyrics": data.get("lyrics"),
                "playlistId": data.get("playlistId")}

    def lyrics_browse_id(self, video_id: str) -> str | None:
        return self._cached(("lyrics-id", video_id),
                            lambda: self.client.get_watch_playlist(videoId=video_id, limit=1).get("lyrics") or "")

    def lyrics(self, browse_id: str):
        return self.client.get_lyrics(browse_id, timestamps=True)

    # -- account ----------------------------------------------------------
    def account_info(self) -> dict:
        info = self.client.get_account_info()
        return {"name": info.get("accountName"), "handle": info.get("channelHandle"),
                "photo": info.get("accountPhotoUrl")}

    def account_liked(self) -> list[dict]:
        return models.tracks(self.client.get_liked_songs(limit=500).get("tracks"))

    def account_playlists(self) -> list[dict]:
        return [models.card("playlist", p["playlistId"], p.get("title"),
                            p.get("description") or (p.get("count") and f"{p['count']} songs") or "Playlist",
                            p.get("thumbnails"))
                for p in self.client.get_library_playlists(limit=100) if p.get("playlistId")]

    def account_history(self) -> list[dict]:
        return models.tracks(self.client.get_history())

    def rate(self, video_id: str, liked: bool) -> None:
        self.client.rate_song(video_id, "LIKE" if liked else "INDIFFERENT")
