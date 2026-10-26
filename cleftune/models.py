"""Normalize ytmusicapi's varying result shapes into two UI types.

Track: {"type": "song", videoId, title, artists[{name,id}], artist, album{name,id}|None,
        duration (seconds|None), thumbnail, explicit, isVideo}
Card:  {"type": "album"|"artist"|"playlist", id, title, subtitle, thumbnail}
"""

from __future__ import annotations

import re

_GOOGLE_SIZE = re.compile(r"=w\d+-h\d+")
_GOOGLE_S = re.compile(r"=s\d+")


def best_thumbnail(thumbnails, size: int = 544) -> str | None:
    if isinstance(thumbnails, dict):
        thumbnails = thumbnails.get("thumbnails") or []
    if not thumbnails:
        return None
    url = max(thumbnails, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0)).get("url")
    if not url:
        return None
    if "googleusercontent.com" in url or "ggpht.com" in url:
        if _GOOGLE_SIZE.search(url):
            url = _GOOGLE_SIZE.sub(f"=w{size}-h{size}", url)
        elif _GOOGLE_S.search(url):
            url = _GOOGLE_S.sub(f"=s{size}", url)
    return url


def parse_duration(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    parts = str(value).strip().split(":")
    try:
        seconds = 0
        for part in parts:
            seconds = seconds * 60 + int(part)
        return seconds
    except ValueError:
        return None


def _artists(item: dict) -> list[dict]:
    artists = item.get("artists") or []
    if isinstance(artists, str):
        return [{"name": artists, "id": None}]
    out = [{"name": a.get("name"), "id": a.get("id")} for a in artists if isinstance(a, dict) and a.get("name")]
    if not out and isinstance(item.get("author"), str):
        out = [{"name": item["author"], "id": None}]
    return out


def _album(item: dict) -> dict | None:
    album = item.get("album")
    if isinstance(album, dict) and album.get("name"):
        return {"name": album["name"], "id": album.get("id")}
    if isinstance(album, str) and album:
        return {"name": album, "id": None}
    return None


def track(item: dict, fallback_thumbnail: str | None = None, fallback_album: dict | None = None) -> dict | None:
    video_id = item.get("videoId")
    if not video_id:
        return None
    artists = _artists(item)
    duration = item.get("duration_seconds")
    if duration is None:
        duration = parse_duration(item.get("duration") or item.get("length"))
    video_type = item.get("videoType") or ""
    return {
        "type": "song",
        "videoId": video_id,
        "title": item.get("title") or "Unknown",
        "artists": artists,
        "artist": ", ".join(a["name"] for a in artists) or "",
        "album": _album(item) or fallback_album,
        "duration": duration,
        "thumbnail": best_thumbnail(item.get("thumbnails") or item.get("thumbnail"), 226) or fallback_thumbnail,
        "explicit": bool(item.get("isExplicit")),
        "isVideo": item.get("resultType") == "video" or video_type in ("MUSIC_VIDEO_TYPE_OMV", "MUSIC_VIDEO_TYPE_UGC"),
    }


def tracks(items, **kwargs) -> list[dict]:
    out = []
    for item in items or []:
        if item.get("isAvailable") is False:
            continue
        t = track(item, **kwargs)
        if t:
            out.append(t)
    return out


def _subtitle(*parts) -> str:
    return " • ".join(str(p) for p in parts if p)


def card(kind: str, item_id: str, title: str, subtitle: str = "", thumbnail=None) -> dict:
    return {"type": kind, "id": item_id, "title": title or "", "subtitle": subtitle or "",
            "thumbnail": best_thumbnail(thumbnail) if not isinstance(thumbnail, str) else thumbnail}


def parse_count(value) -> int | None:
    """"7B", "1.2M", "155K", "1,234" (plays/views as YouTube Music shows them) -> a number."""
    if isinstance(value, (int, float)):
        return int(value)
    m = re.match(r"\s*([\d.,]+)\s*([KMB]?)", str(value or ""), re.I)
    if not m:
        return None
    digits, unit = m.group(1), m.group(2).upper()
    try:
        number = float(digits.replace(",", "")) if unit else float(digits.replace(",", "").replace(".", ""))
    except ValueError:
        return None
    return int(number * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[unit])


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", (text or "").casefold())


def rank_by_popularity(items: list[dict], query: str) -> list[dict]:
    """Most played first, but songs that match every word of the query stay ahead of more popular
    songs that don't (searching "believer" shouldn't put a hit called "Believe" on top)."""
    wanted = set(_words(query))

    def relevant(t: dict) -> bool:
        have = set(_words(" ".join([t.get("title") or "", t.get("artist") or "", (t.get("album") or {}).get("name") or ""])))
        return all(any(h.startswith(w) for h in have) for w in wanted)

    return sorted(items, key=lambda t: (not relevant(t), -(t.get("views") or 0)))


def from_search(item: dict) -> dict | None:
    kind = item.get("resultType")
    if kind in ("song", "video", "episode"):
        t = track(item)
        if t and kind == "video":
            t["isVideo"] = True
        if t and parse_count(item.get("views")) is not None:
            t["views"] = parse_count(item.get("views"))
        return t
    if kind == "album" and item.get("browseId"):
        artist = ", ".join(a["name"] for a in _artists(item))
        return card("album", item["browseId"], item.get("title"),
                    _subtitle(item.get("type") or "Album", artist, item.get("year")), item.get("thumbnails"))
    if kind == "artist":
        artist_id = item.get("browseId") or next((a.get("id") for a in item.get("artists") or [] if a.get("id")), None)
        name = item.get("artist") or next((a.get("name") for a in item.get("artists") or []), None)
        if artist_id and name:
            return card("artist", artist_id, name, _subtitle("Artist", item.get("subscribers") and
                                                            f"{item['subscribers']} subscribers"),
                        item.get("thumbnails"))
    if kind == "playlist" and item.get("browseId"):
        return card("playlist", item["browseId"], item.get("title"),
                    _subtitle("Playlist", item.get("author") if isinstance(item.get("author"), str) else
                              ", ".join(a["name"] for a in _artists(item))), item.get("thumbnails"))
    return None


def from_shelf(item: dict) -> dict | None:
    """Items in home/explore/artist shelves carry no resultType; infer it from their IDs."""
    if item.get("videoId"):
        return track(item)
    browse_id = item.get("browseId") or ""
    subtitle = item.get("description") or item.get("year") or ", ".join(a["name"] for a in _artists(item))
    if browse_id.startswith("MPRE"):
        return card("album", browse_id, item.get("title"), _subtitle("Album", subtitle), item.get("thumbnails"))
    if browse_id.startswith("UC"):
        return card("artist", browse_id, item.get("title"), item.get("subscribers") or "Artist",
                    item.get("thumbnails"))
    playlist_id = item.get("playlistId") or (browse_id if browse_id.startswith("VL") else None)
    if playlist_id:
        return card("playlist", playlist_id, item.get("title"), _subtitle("Playlist", subtitle),
                    item.get("thumbnails"))
    return None


def shelf(title: str, items) -> dict | None:
    contents = [x for x in (from_shelf(i) for i in items or []) if x]
    if not contents:
        return None
    return {"title": title, "items": contents}
