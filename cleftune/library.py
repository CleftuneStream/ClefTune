"""Local library stored in SQLite: songs, likes, playlists, history, saved items, downloads."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from .config import data_dir

SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    video_id TEXT PRIMARY KEY, title TEXT NOT NULL, artists TEXT NOT NULL, album TEXT,
    duration INTEGER, thumbnail TEXT, explicit INTEGER DEFAULT 0, is_video INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS liked (video_id TEXT PRIMARY KEY, liked_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS playlist_tracks (
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    position INTEGER NOT NULL, video_id TEXT NOT NULL, PRIMARY KEY (playlist_id, position)
);
CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, video_id TEXT NOT NULL, played_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS history_played ON history(played_at);
CREATE TABLE IF NOT EXISTS saved (
    kind TEXT NOT NULL, id TEXT NOT NULL, title TEXT, subtitle TEXT, thumbnail TEXT, saved_at REAL NOT NULL,
    PRIMARY KEY (kind, id)
);
CREATE TABLE IF NOT EXISTS cached (
    video_id TEXT PRIMARY KEY, path TEXT, size INTEGER DEFAULT 0, last_played REAL NOT NULL, cached_at REAL
);
CREATE TABLE IF NOT EXISTS lyrics_offsets (video_id TEXT PRIMARY KEY, offset REAL NOT NULL);
CREATE TABLE IF NOT EXISTS downloads (
    video_id TEXT PRIMARY KEY, path TEXT, status TEXT NOT NULL, progress REAL DEFAULT 0,
    error TEXT, added_at REAL NOT NULL
);
"""


class Library:
    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / "library.db"
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.executescript(SCHEMA)
            self._db.commit()

    def _q(self, sql: str, args=()) -> list[sqlite3.Row]:
        with self._lock:
            rows = self._db.execute(sql, args).fetchall()
            self._db.commit()
            return rows

    # -- songs ------------------------------------------------------------
    def upsert(self, tracks) -> None:
        if isinstance(tracks, dict):
            tracks = [tracks]
        rows = [(t["videoId"], t.get("title") or "Unknown", json.dumps(t.get("artists") or []),
                 json.dumps(t.get("album")) if t.get("album") else None, t.get("duration"), t.get("thumbnail"),
                 int(bool(t.get("explicit"))), int(bool(t.get("isVideo")))) for t in tracks if t.get("videoId")]
        with self._lock:
            self._db.executemany(
                "INSERT INTO songs VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(video_id) DO UPDATE SET "
                "title=excluded.title, artists=excluded.artists, album=COALESCE(excluded.album, songs.album), "
                "duration=COALESCE(excluded.duration, songs.duration), "
                "thumbnail=COALESCE(excluded.thumbnail, songs.thumbnail), explicit=excluded.explicit, "
                "is_video=excluded.is_video", rows)
            self._db.commit()

    @staticmethod
    def _track(row: sqlite3.Row) -> dict:
        artists = json.loads(row["artists"] or "[]")
        return {
            "type": "song", "videoId": row["video_id"], "title": row["title"], "artists": artists,
            "artist": ", ".join(a.get("name", "") for a in artists),
            "album": json.loads(row["album"]) if row["album"] else None, "duration": row["duration"],
            "thumbnail": row["thumbnail"], "explicit": bool(row["explicit"]), "isVideo": bool(row["is_video"]),
        }

    def song(self, video_id: str) -> dict | None:
        rows = self._q("SELECT * FROM songs WHERE video_id=?", (video_id,))
        return self._track(rows[0]) if rows else None

    # -- likes ------------------------------------------------------------
    def set_liked(self, track: dict, liked: bool) -> None:
        if liked:
            self.upsert(track)
            self._q("INSERT OR IGNORE INTO liked VALUES (?,?)", (track["videoId"], time.time()))
        else:
            self._q("DELETE FROM liked WHERE video_id=?", (track["videoId"],))

    def is_liked(self, video_id: str) -> bool:
        return bool(self._q("SELECT 1 FROM liked WHERE video_id=?", (video_id,)))

    def liked_ids(self) -> list[str]:
        return [r[0] for r in self._q("SELECT video_id FROM liked")]

    def liked(self) -> list[dict]:
        return [self._track(r) for r in self._q(
            "SELECT s.* FROM liked l JOIN songs s USING(video_id) ORDER BY l.liked_at DESC")]

    # -- playlists --------------------------------------------------------
    def playlists(self) -> list[dict]:
        rows = self._q("SELECT p.id, p.name, COUNT(t.video_id) AS n, "
                       "(SELECT s.thumbnail FROM playlist_tracks t2 JOIN songs s USING(video_id) "
                       " WHERE t2.playlist_id=p.id ORDER BY t2.position LIMIT 1) AS thumb "
                       "FROM playlists p LEFT JOIN playlist_tracks t ON t.playlist_id=p.id "
                       "GROUP BY p.id ORDER BY p.updated_at DESC")
        return [{"type": "local-playlist", "id": str(r["id"]), "title": r["name"],
                 "subtitle": f"{r['n']} songs", "thumbnail": r["thumb"]} for r in rows]

    def playlist(self, playlist_id: int) -> dict | None:
        meta = self._q("SELECT * FROM playlists WHERE id=?", (playlist_id,))
        if not meta:
            return None
        tracks = [self._track(r) for r in self._q(
            "SELECT s.* FROM playlist_tracks t JOIN songs s USING(video_id) WHERE t.playlist_id=? "
            "ORDER BY t.position", (playlist_id,))]
        return {"type": "local-playlist", "id": str(playlist_id), "title": meta[0]["name"],
                "subtitle": f"Your playlist • {len(tracks)} songs",
                "thumbnail": tracks[0]["thumbnail"] if tracks else None, "tracks": tracks}

    def create_playlist(self, name: str, tracks=()) -> int:
        now = time.time()
        with self._lock:
            cur = self._db.execute("INSERT INTO playlists (name, created_at, updated_at) VALUES (?,?,?)",
                                   (name.strip() or "New playlist", now, now))
            self._db.commit()
            playlist_id = cur.lastrowid
        if tracks:
            self.add_to_playlist(playlist_id, tracks)
        return playlist_id

    def rename_playlist(self, playlist_id: int, name: str) -> None:
        self._q("UPDATE playlists SET name=?, updated_at=? WHERE id=?", (name.strip(), time.time(), playlist_id))

    def delete_playlist(self, playlist_id: int) -> None:
        self._q("DELETE FROM playlists WHERE id=?", (playlist_id,))

    def add_to_playlist(self, playlist_id: int, tracks) -> int:
        self.upsert(tracks)
        with self._lock:
            start = self._db.execute("SELECT COALESCE(MAX(position)+1, 0) FROM playlist_tracks WHERE playlist_id=?",
                                     (playlist_id,)).fetchone()[0]
            self._db.executemany("INSERT INTO playlist_tracks VALUES (?,?,?)",
                                 [(playlist_id, start + i, t["videoId"]) for i, t in enumerate(tracks)])
            self._db.execute("UPDATE playlists SET updated_at=? WHERE id=?", (time.time(), playlist_id))
            self._db.commit()
        return len(tracks)

    def _rewrite_order(self, playlist_id: int, video_ids: list[str]) -> None:
        with self._lock:
            self._db.execute("DELETE FROM playlist_tracks WHERE playlist_id=?", (playlist_id,))
            self._db.executemany("INSERT INTO playlist_tracks VALUES (?,?,?)",
                                 [(playlist_id, i, v) for i, v in enumerate(video_ids)])
            self._db.execute("UPDATE playlists SET updated_at=? WHERE id=?", (time.time(), playlist_id))
            self._db.commit()

    def _order(self, playlist_id: int) -> list[str]:
        return [r[0] for r in self._q("SELECT video_id FROM playlist_tracks WHERE playlist_id=? ORDER BY position",
                                      (playlist_id,))]

    def remove_from_playlist(self, playlist_id: int, index: int) -> None:
        order = self._order(playlist_id)
        if 0 <= index < len(order):
            del order[index]
            self._rewrite_order(playlist_id, order)

    def move_in_playlist(self, playlist_id: int, src: int, dst: int) -> None:
        order = self._order(playlist_id)
        if 0 <= src < len(order) and 0 <= dst < len(order):
            order.insert(dst, order.pop(src))
            self._rewrite_order(playlist_id, order)

    # -- history & stats --------------------------------------------------
    def add_history(self, track: dict) -> None:
        self.upsert(track)
        last = self._q("SELECT video_id, played_at FROM history ORDER BY id DESC LIMIT 1")
        if last and last[0]["video_id"] == track["videoId"] and time.time() - last[0]["played_at"] < 30:
            return
        self._q("INSERT INTO history (video_id, played_at) VALUES (?,?)", (track["videoId"], time.time()))

    def history(self, limit: int = 200) -> list[dict]:
        rows = self._q("SELECT s.*, h.played_at FROM history h JOIN songs s USING(video_id) "
                       "ORDER BY h.id DESC LIMIT ?", (limit,))
        return [self._track(r) | {"playedAt": r["played_at"]} for r in rows]

    def clear_history(self) -> None:
        self._q("DELETE FROM history")

    def stats(self, days: int = 30) -> dict:
        since = time.time() - days * 86400
        songs = self._q("SELECT s.*, COUNT(*) AS plays FROM history h JOIN songs s USING(video_id) "
                        "WHERE h.played_at>=? GROUP BY h.video_id ORDER BY plays DESC LIMIT 25", (since,))
        rows = self._q("SELECT s.artists, s.duration FROM history h JOIN songs s USING(video_id) WHERE h.played_at>=?",
                       (since,))
        artists: dict[str, dict] = {}
        total_seconds = 0
        for r in rows:
            total_seconds += r["duration"] or 0
            for a in json.loads(r["artists"] or "[]")[:1]:
                entry = artists.setdefault(a.get("name"), {"name": a.get("name"), "id": a.get("id"), "plays": 0})
                entry["plays"] += 1
        return {
            "days": days, "plays": len(rows), "minutes": round(total_seconds / 60),
            "songs": [self._track(r) | {"plays": r["plays"]} for r in songs],
            "artists": sorted(artists.values(), key=lambda a: -a["plays"])[:15],
        }

    # -- saved albums / artists / playlists -------------------------------
    def save(self, item: dict) -> None:
        self._q("INSERT OR REPLACE INTO saved VALUES (?,?,?,?,?,?)",
                (item["type"], item["id"], item.get("title"), item.get("subtitle"), item.get("thumbnail"), time.time()))

    def unsave(self, kind: str, item_id: str) -> None:
        self._q("DELETE FROM saved WHERE kind=? AND id=?", (kind, item_id))

    def is_saved(self, kind: str, item_id: str) -> bool:
        return bool(self._q("SELECT 1 FROM saved WHERE kind=? AND id=?", (kind, item_id)))

    def saved(self) -> list[dict]:
        return [{"type": r["kind"], "id": r["id"], "title": r["title"], "subtitle": r["subtitle"],
                 "thumbnail": r["thumbnail"]} for r in self._q("SELECT * FROM saved ORDER BY saved_at DESC")]

    # -- downloads --------------------------------------------------------
    def set_download(self, video_id: str, status: str, path: str | None = None, progress: float = 0,
                     error: str | None = None) -> None:
        self._q("INSERT INTO downloads VALUES (?,?,?,?,?,?) ON CONFLICT(video_id) DO UPDATE SET "
                "path=COALESCE(excluded.path, downloads.path), status=excluded.status, "
                "progress=excluded.progress, error=excluded.error",
                (video_id, path, status, progress, error, time.time()))

    def download_path(self, video_id: str) -> str | None:
        rows = self._q("SELECT path FROM downloads WHERE video_id=? AND status='done'", (video_id,))
        return rows[0]["path"] if rows else None

    def download_ids(self) -> list[str]:
        return [r[0] for r in self._q("SELECT video_id FROM downloads WHERE status='done'")]

    def downloads(self) -> list[dict]:
        rows = self._q("SELECT d.*, s.* FROM downloads d JOIN songs s USING(video_id) ORDER BY d.added_at DESC")
        return [self._track(r) | {"status": r["status"], "progress": r["progress"], "error": r["error"],
                                  "path": r["path"]} for r in rows]

    def delete_download(self, video_id: str) -> str | None:
        rows = self._q("SELECT path FROM downloads WHERE video_id=?", (video_id,))
        self._q("DELETE FROM downloads WHERE video_id=?", (video_id,))
        return rows[0]["path"] if rows else None

    def reset_stale_downloads(self) -> list[str]:
        rows = self._q("SELECT video_id FROM downloads WHERE status IN ('queued','downloading')")
        return [r[0] for r in rows]

    # -- song cache (recently played, for offline) -------------------------
    def cache_touch(self, video_id: str) -> None:
        self._q("INSERT INTO cached (video_id, last_played) VALUES (?,?) ON CONFLICT(video_id) DO UPDATE SET "
                "last_played=excluded.last_played", (video_id, time.time()))

    def cache_set_file(self, video_id: str, path: str | None, size: int = 0) -> None:
        self._q("UPDATE cached SET path=?, size=?, cached_at=? WHERE video_id=?",
                (path, size, time.time() if path else None, video_id))

    def cache_path(self, video_id: str) -> str | None:
        rows = self._q("SELECT path FROM cached WHERE video_id=? AND path IS NOT NULL", (video_id,))
        return rows[0]["path"] if rows else None

    def cache_entries(self) -> list[dict]:
        """Newest first, including songs not cached yet."""
        return [dict(r) for r in self._q("SELECT * FROM cached ORDER BY last_played DESC")]

    def cache_forget(self, video_id: str) -> None:
        self._q("DELETE FROM cached WHERE video_id=?", (video_id,))

    def cached_tracks(self) -> list[dict]:
        rows = self._q("SELECT s.*, c.size, c.last_played FROM cached c JOIN songs s USING(video_id) "
                       "WHERE c.path IS NOT NULL ORDER BY c.last_played DESC")
        return [self._track(r) | {"size": r["size"], "lastPlayed": r["last_played"]} for r in rows]

    # -- lyrics timing corrections -----------------------------------------
    def lyrics_offset(self, video_id: str) -> float:
        rows = self._q("SELECT offset FROM lyrics_offsets WHERE video_id=?", (video_id,))
        return rows[0]["offset"] if rows else 0.0

    def set_lyrics_offset(self, video_id: str, offset: float) -> None:
        if abs(offset) < 0.001:
            self._q("DELETE FROM lyrics_offsets WHERE video_id=?", (video_id,))
        else:
            self._q("INSERT OR REPLACE INTO lyrics_offsets VALUES (?,?)", (video_id, offset))

    def close(self) -> None:
        with self._lock:
            self._db.close()
