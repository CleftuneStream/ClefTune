"""Lyrics: synced sources first (LRCLIB, YouTube Music, KuGou), plain text as fallback.

Word-by-word timing comes from the source when it has it (KuGou KRC, enhanced LRC). Line-only
lyrics borrow KuGou's word timing when its text matches, and otherwise get an estimate.
Results are stored on disk so lyrics also work offline for cached songs.
"""

from __future__ import annotations

import base64
import json
import re
import statistics
import urllib.error
import urllib.parse
import urllib.request
import zlib

from . import __version__
from .config import cache_dir
from .ytm import TTLCache, YTM

LRCLIB = "https://lrclib.net/api"
USER_AGENT = f"ClefTune/{__version__} (unofficial YouTube Music client)"
_TIMESTAMP = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")
_WORD_STAMP = re.compile(r"<(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?>")
_OFFSET = re.compile(r"\[offset:\s*([+-]?\d+)\]", re.I)
_NOISE = re.compile(r"\s*[\(\[](?:feat\.?|ft\.?|with|official|lyric|audio|video|visualizer|remaster)[^\)\]]*[\)\]]", re.I)
_KUGOU_CREDIT = re.compile(r".+[:：].+")              # "作词 : name" / "Lyrics by：name" credit lines
_KRC_KEY = bytes([64, 71, 97, 119, 94, 50, 116, 71, 81, 54, 49, 45, 206, 210, 110, 105])
_KRC_LINE = re.compile(r"^\[(\d+),(\d+)\](.*)$")     # [line start ms, line duration ms]
_KRC_WORD = re.compile(r"<(\d+),(\d+),\d+>([^<]*)")   # <offset from line start ms, duration ms, 0>word
_CJK = "぀-ヿ㐀-䶿一-鿿가-힯豈-﫿"
_CJK_RE = re.compile(f"[{_CJK}]")
_TOKEN = re.compile(f"[{_CJK}]\\s*|[^\\s{_CJK}]+\\s*")
_VOWELS = re.compile(r"[aeiouyàáâãäåæèéêëìíîïòóôõöøùúûüýÿ]+", re.I)
CACHE_VERSION = 2                                      # bump when stored results should be refetched
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


def decode_krc(content: bytes) -> str:
    """KuGou KRC: 'krc1' magic, then zlib data XOR-ed with a fixed 16-byte key."""
    if content[:4] != b"krc1":
        raise ValueError("not a KRC file")
    body = bytes(b ^ _KRC_KEY[i % 16] for i, b in enumerate(content[4:]))
    return zlib.decompress(body).decode("utf-8", "replace")


def parse_krc(text: str) -> list[dict]:
    """Parse decoded KRC into the same shape as parse_lrc, with real per-word start and duration."""
    lines = []
    for raw in text.splitlines():
        m = _KRC_LINE.match(raw.strip().lstrip("﻿"))
        if not m:
            continue
        start = int(m.group(1)) / 1000
        words = [{"t": round(start + int(w.group(1)) / 1000, 3), "d": round(int(w.group(2)) / 1000, 3), "text": w.group(3)}
                 for w in _KRC_WORD.finditer(m.group(3)) if w.group(3)]
        lyric = "".join(w["text"] for w in words).strip()
        line = {"t": round(start, 3), "text": lyric}
        if lyric:
            line["words"] = words
        lines.append(line)
    lines.sort(key=lambda line: line["t"])
    return lines


def _without_credits(lines: list[dict]) -> list[dict]:
    """Drop writer/composer credits: everything up to the last credit line near the start/end."""
    head = [i for i in range(min(30, len(lines))) if _KUGOU_CREDIT.match(lines[i]["text"])]
    lines = lines[head[-1] + 1:] if head else lines
    tail = [i for i in range(max(0, len(lines) - 30), len(lines)) if _KUGOU_CREDIT.match(lines[i]["text"])]
    return lines[:tail[0]] if tail else lines


def _norm(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.casefold())


def same_lyrics(a: list[dict], b: list[dict]) -> bool:
    """True when b holds the same lines as a, at roughly the same times (safe to swap a for b)."""
    times_b: dict[str, list[float]] = {}
    for line in b:
        times_b.setdefault(_norm(line["text"]), []).append(line["t"])
    keys_a = [(_norm(line["text"]), line["t"]) for line in a if _norm(line["text"])]
    if not keys_a:
        return False
    # repeated lines (choruses) are compared with their nearest occurrence, not the first one
    drift = [min(abs(tb - t) for tb in times_b[k]) for k, t in keys_a if k in times_b]
    if not drift:
        return False
    count_b = sum(1 for line in b if _norm(line["text"]))
    return (len(drift) / len(keys_a) >= 0.6 and 0.6 <= count_b / len(keys_a) <= 1.6
            and statistics.median(drift) <= 1.5)


def _syllables(token: str) -> float:
    core = re.sub(r"[\W\d_]", "", token)
    if not core:
        return 0.3                                   # punctuation: a short beat
    if _CJK_RE.search(core):
        return 1.0                                   # one character, one sung syllable
    n = len(_VOWELS.findall(core))
    if n > 1 and core.lower().endswith("e") and not core.lower().endswith(("le", "ee")):
        n -= 1                                       # silent final e: "make", "time"
    return float(n or max(1, round(len(core) / 3)))  # scripts without Latin vowels: rough length guess


def estimate_words(lines: list[dict]) -> bool:
    """Give line-only lyrics a per-word timeline. Words are spread by syllable count at a typical
    singing pace (~3 syllables a second) so a long instrumental gap holds the last word instead of
    slowing the whole line down. Returns True if any line was estimated."""
    changed = False
    for i, line in enumerate(lines):
        if line.get("words") or not line["text"].strip():
            continue
        tokens = _TOKEN.findall(line["text"])
        weights = [_syllables(tok) for tok in tokens]
        total = sum(weights)
        if not total:
            continue
        nxt = next((l["t"] for l in lines[i + 1:] if l["t"] > line["t"]), None)
        gap = nxt - line["t"] if nxt is not None else 4.0
        span = min(gap * 0.92, max(0.6, total * 0.32 + 0.25))
        words, done = [], 0.0
        for tok, weight in zip(tokens, weights):
            words.append({"t": round(line["t"] + span * done / total, 3), "d": round(span * weight / total, 3), "text": tok})
            done += weight
        line["words"] = words
        changed = True
    return changed


def _fill_durations(lines: list[dict]) -> None:
    """Enhanced LRC only gives word starts: each word lasts until the next one (or the line's end)."""
    for i, line in enumerate(lines):
        words = line.get("words")
        if not words:
            continue
        line_end = next((l["t"] for l in lines[i + 1:] if l["t"] > line["t"]), words[-1]["t"] + 1.0)
        for k, word in enumerate(words):
            if "d" not in word:
                until = words[k + 1]["t"] if k + 1 < len(words) else min(line_end, word["t"] + 1.0)
                word["d"] = round(max(0.05, until - word["t"]), 3)


def prepare(result: dict, estimate: bool) -> dict:
    """Copy a stored result for the UI: word durations filled in, estimates added if wanted,
    and "wordSync" set to "exact", "estimated" or None."""
    out = json.loads(json.dumps(result))             # deep copy that also un-shares repeated lines' word lists
    lines = out.get("lines") or []
    exact = any(line.get("words") for line in lines)
    estimated = False
    if out.get("synced") and lines:
        _fill_durations(lines)
        if estimate:
            estimated = estimate_words(lines)
    out["wordSync"] = "exact" if exact else ("estimated" if estimated else None)
    return out


def clean_title(title: str) -> str:
    return _NOISE.sub("", title).strip()


class LyricsService:
    def __init__(self, ytm: YTM):
        self.ytm = ytm
        self._cache = TTLCache(ttl=3600, max_items=200)
        self.folder = cache_dir() / "lyrics"
        self.folder.mkdir(parents=True, exist_ok=True)

    def get(self, track: dict, estimate: bool = True) -> dict:
        key = track["videoId"]
        hit = self._cache.get(key)
        if hit is None:
            hit = self._load(track)
            self._cache.put(key, hit)
        return prepare(hit, estimate)

    def _load(self, track: dict) -> dict:
        stored = self.folder / f"{track['videoId']}.json"
        try:
            old = json.loads(stored.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            old = None
        if old is not None and old.get("v") == CACHE_VERSION:
            return old
        result = self._fetch(track)
        if result.get("source"):                # only remember real results (not "offline, none found")
            result["v"] = CACHE_VERSION
            stored.write_text(json.dumps(result), encoding="utf-8")
            return result
        return old or result                    # offline: an older stored copy beats nothing

    def _fetch(self, track: dict) -> dict:
        plain = None
        for name, source in (("lrclib", self._lrclib), ("ytm", lambda t: self._ytm(t["videoId"])), ("kugou", self._kugou)):
            result = source(track)
            if result and result.get("synced"):
                if name != "kugou" and not any(line.get("words") for line in result["lines"]):
                    result = self._with_word_timing(track, result)
                return result
            plain = plain or result
        return plain or NO_LYRICS

    def _with_word_timing(self, track: dict, result: dict) -> dict:
        """Line-synced lyrics: use KuGou's word-timed copy instead when it's the same song text."""
        kugou = self._kugou(track)
        if kugou and any(line.get("words") for line in kugou["lines"]) and same_lyrics(result["lines"], kugou["lines"]):
            return kugou
        return result

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
            lines = self._kugou_download(candidate)
        except (OSError, ValueError, KeyError):
            return None
        lines = [l for l in _without_credits(lines) if l["text"]]
        if len(lines) < 3:
            return None
        return {"source": "KuGou", "synced": True, "lines": lines, "text": ""}

    def _kugou_download(self, candidate: dict) -> list[dict]:
        """KRC (word-timed) first, plain LRC if KRC is missing or unreadable."""
        params = {"charset": "utf8", "client": "pc", "ver": 1, "id": candidate["id"], "accesskey": candidate["accesskey"]}
        try:
            data = self._kugou_get("https://lyrics.kugou.com/download", params | {"fmt": "krc"})
            lines = parse_krc(decode_krc(base64.b64decode(data.get("content") or "")))
            if lines:
                return lines
        except (ValueError, zlib.error):
            pass
        data = self._kugou_get("https://lyrics.kugou.com/download", params | {"fmt": "lrc"})
        lrc = base64.b64decode(data.get("content") or "").decode("utf-8", "replace")
        return parse_lrc("\n".join(r for r in lrc.splitlines() if _TIMESTAMP.match(r)))
