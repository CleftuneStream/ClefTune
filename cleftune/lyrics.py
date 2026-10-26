"""Lyrics: synced sources first (LRCLIB, YouTube Music, KuGou), plain text as fallback.

Results are stored on disk so lyrics also work offline for cached songs.
"""

from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from . import __version__
from .config import cache_dir
from .ytm import TTLCache, YTM

LRCLIB = "https://lrclib.net/api"
USER_AGENT = f"ClefTune/{__version__} (unofficial YouTube Music client)"
_TIMESTAMP = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")
_WORD_STAMP = re.compile(r"<(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?>")
_OFFSET = re.compile(r"\[offset:\s*([+-]?\d+)\]", re.I)
_NOISE = re.compile(r"\s*[\(\[](?:feat\.?|ft\.?|with|official|lyric|audio|video|visualizer|remaster)[^\)\]]*[\)\]]", re.I)
_KUGOU_CREDIT = re.compile(r".+\].+[:：].+")          # "[00:01.00]作词 : name" style credit lines
NO_LYRICS = {"source": None, "synced": False, "lines": [], "text": ""}


def _seconds(m: re.Match) -> float:
    frac = m.group(3) or "0"
    return int(m.group(1)) * 60 + int(m.group(2)) + int(frac) / (10 ** len(frac))


def parse_lrc(text: str) -> list[dict]:
    """Parse LRC into [{"t": seconds, "text": str, "words"?: [{"t", "text"}]}], sorted.

    Lines may carry several timestamps; enhanced LRC <mm:ss.xx> tags give per-word timing.
    """
    offset_match = _OFFSET.search(text)
    offset = int(offset_match.group(1)) / 1000 if offset_match else 0.0
    lines = []
    for raw in text.splitlines():
        stamps = list(_TIMESTAMP.finditer(raw))
        if not stamps:
            continue
        lyric = raw[stamps[-1].end():].strip()
        words = None
        word_stamps = list(_WORD_STAMP.finditer(lyric))
        if word_stamps:
            words = []
            for i, m in enumerate(word_stamps):
                end = word_stamps[i + 1].start() if i + 1 < len(word_stamps) else len(lyric)
                chunk = lyric[m.end():end]
                if chunk.strip():
                    words.append({"t": max(0.0, round(_seconds(m) - offset, 3)), "text": chunk})
            lyric = _WORD_STAMP.sub("", lyric).strip()
        for m in stamps:
            line = {"t": max(0.0, round(_seconds(m) - offset, 3)), "text": lyric}
            if words:
                line["words"] = words
            lines.append(line)
    lines.sort(key=lambda line: line["t"])
    return lines


def clean_title(title: str) -> str:
    return _NOISE.sub("", title).strip()


class LyricsService:
    def __init__(self, ytm: YTM):
        self.ytm = ytm
        self._cache = TTLCache(ttl=3600, max_items=200)
        self.folder = cache_dir() / "lyrics"
        self.folder.mkdir(parents=True, exist_ok=True)

    def get(self, track: dict) -> dict:
        key = track["videoId"]
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        stored = self.folder / f"{key}.json"
        try:
            result = json.loads(stored.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            result = self._fetch(track)
            if result.get("source"):            # only remember real results (not "offline, none found")
                stored.write_text(json.dumps(result), encoding="utf-8")
        self._cache.put(key, result)
        return result

    def _fetch(self, track: dict) -> dict:
        plain = None
        for source in (self._lrclib, lambda t: self._ytm(t["videoId"]), self._kugou):
            result = source(track)
            if result and result.get("synced"):
                return result
            plain = plain or result
        return plain or NO_LYRICS

    def _ytm(self, video_id: str) -> dict | None:
        try:
            browse_id = self.ytm.lyrics_browse_id(video_id)
            if not browse_id:
                return None
            data = self.ytm.lyrics(browse_id)
        except Exception:
            return None
        if not data:
            return None
        source = (data.get("source") or "YouTube Music").replace("Source: ", "")
        content = data.get("lyrics")
        if isinstance(content, list):
            lines = []
            for line in content:
                get = line.get if isinstance(line, dict) else lambda k, line=line: getattr(line, k, None)
                start = get("start_time")
                if start is not None:
                    lines.append({"t": start / 1000, "text": get("text") or ""})
            if lines:
                return {"source": source, "synced": True, "lines": lines, "text": ""}
            return None
        if isinstance(content, str) and content.strip():
            return {"source": source, "synced": False, "lines": [], "text": content}
        return None

    def _lrclib_request(self, endpoint: str, params: dict):
        url = f"{LRCLIB}/{endpoint}?{urllib.parse.urlencode({k: v for k, v in params.items() if v})}"
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise

    def _lrclib(self, track: dict) -> dict | None:
        artist = track["artists"][0]["name"] if track.get("artists") else track.get("artist", "")
        title = track.get("title", "")
        duration = track.get("duration")
        album = (track.get("album") or {}).get("name")
        try:
            hit = self._lrclib_request("get", {"track_name": title, "artist_name": artist,
                                               "album_name": album, "duration": duration})
            if not (hit and (hit.get("syncedLyrics") or hit.get("plainLyrics"))):
                results = self._lrclib_request("search", {"track_name": clean_title(title), "artist_name": artist})
                hit = self._pick(results or [], duration)
        except (OSError, ValueError):
            return None
        if not hit:
            return None
        if hit.get("syncedLyrics"):
            lines = parse_lrc(hit["syncedLyrics"])
            if lines:
                return {"source": "LRCLIB", "synced": True, "lines": lines, "text": ""}
        if hit.get("plainLyrics"):
            return {"source": "LRCLIB", "synced": False, "lines": [], "text": hit["plainLyrics"]}
        return None

    @staticmethod
    def _pick(results: list, duration) -> dict | None:
        def score(r):
            delta = abs((r.get("duration") or 0) - duration) if duration else 0
            return (delta > 5, not r.get("syncedLyrics"), delta)
        candidates = [r for r in results if r.get("syncedLyrics") or r.get("plainLyrics")]
        if duration:
            candidates = [r for r in candidates if abs((r.get("duration") or 0) - duration) <= 10]
        return min(candidates, key=score) if candidates else None

    # -- KuGou (large synced catalogue, strong for Asian music) -----------
    @staticmethod
    def _kugou_get(url: str, params: dict) -> dict:
        full = f"{url}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"
        req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))

    def _kugou(self, track: dict) -> dict | None:
        artist = re.sub(r"\(.*?\)", "", track.get("artist") or "").replace(", ", "、").replace(" & ", "、").strip()
        title = re.sub(r"[\(（「『<《〈＜].*?[\)）」』>》〉＞]", "", track.get("title") or "").strip()
        duration = track.get("duration") or 0
        keyword = f"{title} - {artist}"
        try:
            candidate = None
            songs = self._kugou_get("https://mobileservice.kugou.com/api/v3/search/song",
                                    {"version": 9108, "plat": 0, "pagesize": 8, "showtype": 0, "keyword": keyword})
            for song in (songs.get("data") or {}).get("info") or []:
                if duration and abs(song.get("duration", 0) - duration) > 8:
                    continue
                found = self._kugou_get("https://lyrics.kugou.com/search",
                                        {"ver": 1, "man": "yes", "client": "pc", "hash": song.get("hash", "")})
                if found.get("candidates"):
                    candidate = found["candidates"][0]
                    break
            if candidate is None:
                params = {"ver": 1, "man": "yes", "client": "pc", "keyword": keyword}
                if duration:
                    params["duration"] = duration * 1000
                found = self._kugou_get("https://lyrics.kugou.com/search", params)
                candidate = (found.get("candidates") or [None])[0]
            if not candidate:
                return None
            data = self._kugou_get("https://lyrics.kugou.com/download",
                                   {"fmt": "lrc", "charset": "utf8", "client": "pc", "ver": 1,
                                    "id": candidate["id"], "accesskey": candidate["accesskey"]})
            lrc = base64.b64decode(data.get("content") or "").decode("utf-8", "replace")
        except (OSError, ValueError, KeyError):
            return None
        rows = [r for r in lrc.splitlines() if _TIMESTAMP.match(r)]
        # drop writer/composer credits: everything up to the last credit line near the start/end
        head = [i for i in range(min(30, len(rows))) if _KUGOU_CREDIT.match(rows[i])]
        rows = rows[head[-1] + 1:] if head else rows
        tail = [i for i in range(max(0, len(rows) - 30), len(rows)) if _KUGOU_CREDIT.match(rows[i])]
        rows = rows[:tail[0]] if tail else rows
        lines = [l for l in parse_lrc("\n".join(rows)) if l["text"]]
        if len(lines) < 3:
            return None
        return {"source": "KuGou", "synced": True, "lines": lines, "text": ""}
