import threading
import time

import pytest

from cleftune import models
from cleftune.events import EventBus
from cleftune.library import Library
from cleftune.lyrics import LyricsService, clean_title, parse_lrc
from cleftune.player import Player
from cleftune.streams import StreamInfo


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setenv("CLEFTUNE_DATA_DIR", str(tmp_path))


def song(vid, title=None, artist="Artist", duration=200):
    return {"type": "song", "videoId": vid, "title": title or f"Song {vid}", "artists": [{"name": artist, "id": "UC1"}],
            "artist": artist, "album": None, "duration": duration, "thumbnail": None, "explicit": False, "isVideo": False}


# ---------------------------------------------------------------- models
def test_best_thumbnail_upscales_google_images():
    thumbs = [{"url": "https://lh3.googleusercontent.com/x=w60-h60-l90-rj", "width": 60, "height": 60}]
    assert models.best_thumbnail(thumbs) == "https://lh3.googleusercontent.com/x=w544-h544-l90-rj"


def test_parse_duration():
    assert models.parse_duration("3:32") == 212
    assert models.parse_duration("1:02:03") == 3723
    assert models.parse_duration("live") is None


def test_search_top_result_artist_without_browse_id():
    item = {"category": "Top result", "resultType": "artist", "artists": [{"name": "Daft Punk", "id": "UCx"}],
            "thumbnails": []}
    card = models.from_search(item)
    assert card["type"] == "artist" and card["id"] == "UCx" and card["title"] == "Daft Punk"


def test_shelf_inference():
    assert models.from_shelf({"videoId": "abc123def45", "title": "t"})["type"] == "song"
    assert models.from_shelf({"browseId": "MPREb_1", "title": "a"})["type"] == "album"
    assert models.from_shelf({"browseId": "UC123", "title": "x"})["type"] == "artist"
    assert models.from_shelf({"playlistId": "RDCLAK5", "title": "p"})["type"] == "playlist"


def test_unavailable_tracks_are_dropped():
    assert models.tracks([{"videoId": "a1", "isAvailable": False}, {"videoId": "b2", "title": "ok"}])[0]["videoId"] == "b2"


# ---------------------------------------------------------------- lyrics
def test_parse_lrc_multi_stamps_and_offset():
    lrc = "[ar:Someone]\n[offset:+500]\n[00:10.00][00:20.50]Chorus\n[00:05.5]Intro\n[01:00]End"
    lines = parse_lrc(lrc)
    assert [l["text"] for l in lines] == ["Intro", "Chorus", "Chorus", "End"]
    assert lines[0]["t"] == pytest.approx(5.0)       # 5.5 - 0.5 offset
    assert lines[2]["t"] == pytest.approx(20.0)
    assert lines[3]["t"] == pytest.approx(59.5)


def test_clean_title():
    assert clean_title("Get Lucky (feat. Pharrell Williams) [Official Video]") == "Get Lucky"


def test_lrclib_pick_prefers_synced_close_duration():
    results = [{"duration": 300, "syncedLyrics": "[00:01]x"}, {"duration": 201, "plainLyrics": "p"},
               {"duration": 202, "syncedLyrics": "[00:01]y"}]
    assert LyricsService._pick(results, 200)["syncedLyrics"] == "[00:01]y"


# ---------------------------------------------------------------- library
def test_library_likes_playlists_history(tmp_path):
    lib = Library(tmp_path / "lib.db")
    a, b, c = song("aaaaaaaaaa1"), song("bbbbbbbbbb2"), song("cccccccccc3", artist="Other")
    lib.set_liked(a, True)
    assert lib.is_liked(a["videoId"]) and lib.liked()[0]["title"] == a["title"]
    pid = lib.create_playlist("Mix", [a, b, c])
    lib.move_in_playlist(pid, 2, 0)
    assert [t["videoId"] for t in lib.playlist(pid)["tracks"]] == [c["videoId"], a["videoId"], b["videoId"]]
    lib.remove_from_playlist(pid, 1)
    assert [t["videoId"] for t in lib.playlist(pid)["tracks"]] == [c["videoId"], b["videoId"]]
    lib.add_history(a)
    lib.add_history(a)              # immediate repeat is de-duplicated
    lib.add_history(c)
    assert [t["videoId"] for t in lib.history()] == [c["videoId"], a["videoId"]]
    stats = lib.stats()
    assert stats["plays"] == 2 and {x["name"] for x in stats["artists"]} == {"Artist", "Other"}
    lib.save({"type": "album", "id": "MPREb_x", "title": "Album"})
    assert lib.is_saved("album", "MPREb_x")
    lib.set_download(a["videoId"], "done", path="/tmp/a.opus")
    assert lib.download_path(a["videoId"]) == "/tmp/a.opus"


# ---------------------------------------------------------------- player
class FakeEngine:
    name = "fake"

    def __init__(self):
        self.loaded = []
        self.paused = True

    def load(self, url, start=0.0, paused=False):
        self.loaded.append(url)
        self.paused = paused

    def play(self): self.paused = False
    def pause(self): self.paused = True
    def stop(self): self.paused = True
    def seek(self, s): pass
    def set_volume(self, v): pass
    def set_normalize(self, e): pass
    def set_loop(self, enabled): self.loop = enabled
    def shutdown(self): pass


class FakeResolver:
    def __init__(self, fail=()):
        self.fail = set(fail)
        self.invalidated = []

    def resolve(self, vid):
        if vid in self.fail:
            raise RuntimeError("unavailable")
        return StreamInfo(vid, url="https://example.invalid/" + vid, codec="opus", bitrate=128)

    def prefetch(self, vid): pass
    def invalidate(self, vid): self.invalidated.append(vid)


class FakeYTM:
    authenticated = False

    def up_next(self, video_id=None, playlist_id=None, limit=50):
        return {"tracks": [song(f"radio{i:05d}") for i in range(5)], "lyrics": None}


class FakeSettings:
    def __init__(self, **kw):
        self.values = {"volume": 80, "normalize": False, "autoplay": False, "skip_on_error": False,
                       "restore_session": True} | kw

    def get(self, k): return self.values[k]
    def update(self, patch): self.values.update(patch)


def make_player(tmp_path, **settings):
    player = Player(FakeSettings(**settings), Library(tmp_path / "p.db"), FakeYTM(), FakeResolver(), EventBus())
    engine = FakeEngine()
    player.attach(engine, lambda vid, gen: f"/api/stream/{vid}?g={gen}")
    return player, engine


def wait_for(cond, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_play_next_previous_and_repeat(tmp_path):
    player, engine = make_player(tmp_path)
    tracks = [song(f"track{i:06d}") for i in range(3)]
    player.play_tracks(tracks, index=1)
    assert wait_for(lambda: engine.loaded and "track000001" in engine.loaded[-1])
    player.next()
    assert wait_for(lambda: "track000002" in engine.loaded[-1])
    player.next(auto=True)              # end of queue, no repeat, no autoplay -> stops
    assert player.index == 2
    player.set_repeat("all")
    player.next()
    assert wait_for(lambda: "track000000" in engine.loaded[-1])
    player.pos = 10
    player.previous()                   # >3s in: restart same song instead of going back
    assert player.index == 0


def test_shuffle_keeps_current_and_restores_order(tmp_path):
    player, _ = make_player(tmp_path)
    tracks = [song(f"track{i:06d}") for i in range(10)]
    player.play_tracks(tracks, index=4)
    player.set_shuffle(True)
    assert player.index == 0 and player.queue[0]["videoId"] == "track000004"
    assert sorted(t["videoId"] for t in player.queue) == sorted(t["videoId"] for t in tracks)
    player.set_shuffle(False)
    assert [t["videoId"] for t in player.queue] == [t["videoId"] for t in tracks]
    assert player.index == 4


def test_queue_edit_operations(tmp_path):
    player, engine = make_player(tmp_path)
    player.play_tracks([song(f"track{i:06d}") for i in range(4)], index=1)
    player.add_next([song("nextnext001")])
    assert player.queue[2]["videoId"] == "nextnext001"
    player.move(3, 0)                    # move an upcoming song before the current one
    assert player.index == 2 and player.current["videoId"] == "track000001"
    player.remove(0)
    assert player.index == 1 and player.current["videoId"] == "track000001"
    player.remove(player.index)          # removing the current song plays the next one
    assert wait_for(lambda: "nextnext001" in engine.loaded[-1])


def test_radio_fills_queue(tmp_path):
    player, _ = make_player(tmp_path)
    player.play_radio(song("seedseed001"))
    assert wait_for(lambda: len(player.queue) == 6)
    assert player.title.startswith("Radio")


def test_autoplay_extends_at_end(tmp_path):
    player, engine = make_player(tmp_path, autoplay=True)
    player.play_tracks([song("onlyonly001")])
    assert wait_for(lambda: len(player.queue) == 6)   # extended in the background near the end


def test_failed_track_reports_error_and_skips(tmp_path):
    player, engine = make_player(tmp_path, skip_on_error=True)
    player.resolver = FakeResolver(fail={"broken00001"})
    player.play_tracks([song("broken00001"), song("works000002")])
    assert wait_for(lambda: player.error == "unavailable")
    assert wait_for(lambda: engine.loaded and "works000002" in engine.loaded[-1], timeout=5)


def test_engine_error_retries_once_with_fresh_url(tmp_path):
    player, engine = make_player(tmp_path)
    player.play_tracks([song("retryme0001")])
    assert wait_for(lambda: len(engine.loaded) == 1)
    player.on_engine_event("error", message="403")
    assert wait_for(lambda: len(engine.loaded) == 2)
    assert player.resolver.invalidated == ["retryme0001"]


def test_sleep_timer_end_of_song(tmp_path):
    player, engine = make_player(tmp_path)
    player.play_tracks([song("first000001"), song("second00002")])
    assert wait_for(lambda: len(engine.loaded) == 1)
    player.set_sleep(-1)
    player.on_engine_event("ended")
    assert player.index == 0 and engine.paused and not player.sleep_end_of_song


def test_session_roundtrip(tmp_path):
    player, _ = make_player(tmp_path)
    player.play_tracks([song(f"track{i:06d}") for i in range(3)], index=2, title="Saved")
    player.pos = 42.0
    player.save_session()
    restored, _ = make_player(tmp_path)
    restored.restore_session()
    assert restored.index == 2 and restored.pos == 42.0 and restored.title == "Saved"
    assert len(restored.queue) == 3


def test_event_bus_replays_sticky_events():
    bus = EventBus()
    bus.emit("state", {"a": 1}, sticky=True)
    bus.emit("toast", {"m": "x"})
    q = bus.subscribe()
    assert q.get_nowait() == ("state", '{"a":1}')
    assert q.empty()


def test_enhanced_lrc_word_timing():
    line = parse_lrc("[00:12.00]<00:12.00>Hello <00:12.50>dark<00:13.10>ness")[0]
    assert line["text"] == "Hello darkness"
    assert [w["t"] for w in line["words"]] == [12.0, 12.5, 13.1]


def test_repeat_one_loops_inside_engine(tmp_path):
    player, engine = make_player(tmp_path)
    player.play_tracks([song("loopme00001"), song("after000002")])
    assert wait_for(lambda: len(engine.loaded) == 1)
    player.set_repeat("one")
    assert engine.loop is True
    player.set_sleep(-1)                 # "stop after this song" must be able to end the loop
    assert engine.loop is False
    player.set_sleep(0)
    assert engine.loop is True
    player.set_repeat("off")
    assert engine.loop is False


def test_next_two_songs_are_prefetched(tmp_path):
    player, _ = make_player(tmp_path)
    seen = []
    player.resolver.prefetch = lambda vid, head=True: seen.append(vid)
    player.play_tracks([song(f"track{i:06d}") for i in range(4)])
    assert wait_for(lambda: seen == ["track000001", "track000002"])


def test_song_cache_keeps_most_recent(tmp_path):
    from cleftune.song_cache import SongCache
    lib = Library(tmp_path / "c.db")

    class S:
        values = {"cache_enabled": True, "cache_songs": 2}
        def get(self, k): return self.values[k]

    cache = SongCache.__new__(SongCache)          # no worker thread / network
    cache.library, cache.settings, cache.current = lib, S(), None
    for i in range(4):
        vid = f"cached{i:05d}"
        lib.upsert(song(vid))
        lib.cache_touch(vid)
        f = tmp_path / f"{vid}.webm"
        f.write_bytes(b"x")
        lib.cache_set_file(vid, str(f), 1)
        time.sleep(0.01)
    cache.evict()
    assert [t["videoId"] for t in lib.cached_tracks()] == ["cached00003", "cached00002"]
    assert not (tmp_path / "cached00000.webm").exists()


def test_headers_from_cookies():
    from cleftune.auth import headers_from_cookies
    raw = headers_from_cookies({"SAPISID": "abc", "SID": "x"}, "UA")
    assert "cookie: SAPISID=abc; SID=x" in raw and "x-goog-authuser: 0" in raw
    with pytest.raises(ValueError):
        headers_from_cookies({"SID": "x"})


def test_old_metrolist_data_moves_to_cleftune(tmp_path):
    from cleftune.config import _migrate
    old, new = tmp_path / "metrodesk", tmp_path / "cleftune"
    (old / "venv" / "bin").mkdir(parents=True)          # an old from-source install still lives here
    (old / "library.db").write_text("likes")
    _migrate(old, new)
    assert (new / "library.db").read_text() == "likes"
    assert (old / "venv" / "bin").is_dir() and not (new / "venv").exists()
    (new / "library.db").write_text("newer")
    _migrate(old, new)                                    # never overwrites an existing new folder
    assert (new / "library.db").read_text() == "newer"


# ---------------------------------------------------------------- sign-in
def test_cookie_headers_are_recognised_as_browser_login(tmp_path):
    """ytmusicapi 1.12+ treats headers without a SAPISIDHASH Authorization line as OAuth and refuses them."""
    import ytmusicapi
    from ytmusicapi import YTMusic
    from ytmusicapi.auth.auth_parse import determine_auth_type, parse_auth_str
    from ytmusicapi.auth.types import AuthType
    from cleftune.auth import headers_from_cookies
    path = tmp_path / "auth.json"
    ytmusicapi.setup(filepath=str(path), headers_raw=headers_from_cookies({"SAPISID": "abc", "SID": "x"}))
    assert determine_auth_type(parse_auth_str(str(path))[0]) == AuthType.BROWSER
    YTMusic(str(path))                        # used to raise "oauth_credentials not provided"


def test_old_saved_login_is_repaired(tmp_path):
    import json
    from cleftune.config import Settings
    from cleftune.ytm import YTM
    ytm = YTM(Settings())
    ytm.auth_path.write_text(json.dumps({"cookie": "SAPISID=abc; SID=x", "x-goog-authuser": "0",
                                         "origin": "https://music.youtube.com"}))
    ytm._repair_auth_file()
    saved = json.loads(ytm.auth_path.read_text())
    assert saved["authorization"].startswith("SAPISIDHASH ") and "__Secure-3PAPISID=abc" in saved["cookie"]


def test_pasted_headers_get_authorization():
    from cleftune.auth import complete_headers
    out = complete_headers("cookie: SID=1; __Secure-3PAPISID=zz\nx-goog-authuser: 0")
    assert "authorization: SAPISIDHASH " in out
    already = "cookie: SAPISID=a\nauthorization: SAPISIDHASH 1_abc"
    assert complete_headers(already) == already
    with pytest.raises(ValueError):
        complete_headers("cookie: SID=1")


def test_default_browser_mapping(monkeypatch):
    from cleftune import auth
    monkeypatch.setattr(auth, "_os_key", lambda: "linux")
    for desktop, expected in (("brave-browser", "brave"), ("firefox", "firefox"), ("org.mozilla.firefox", "firefox"),
                              ("google-chrome", "chrome"), ("com.brave.Browser", "brave"), ("unknown", None)):
        monkeypatch.setattr(auth, "_default_browser_key", lambda d=desktop: d.lower())
        assert auth.default_browser() == expected
    monkeypatch.setattr(auth, "_os_key", lambda: "win")
    monkeypatch.setattr(auth, "_default_browser_key", lambda: "firefoxurl-308046b0af4a39cb")
    assert auth.default_browser() == "firefox"


def test_browser_login_waits_for_sign_in(monkeypatch):
    """Not signed in yet: open the sign-in page in the browser, then pick the login up once it appears."""
    from cleftune import api as api_mod, auth
    from cleftune.events import EventBus
    calls = {"n": 0}

    def cookies(browser):
        calls["n"] += 1
        if calls["n"] < 3:
            raise auth.NotSignedIn("not yet")
        return {"SAPISID": "abc"}

    opened = []
    monkeypatch.setattr(auth, "installed_browsers", lambda: [{"id": "brave", "label": "Brave", "default": True}])
    monkeypatch.setattr(auth, "cookies_from_browser", cookies)
    monkeypatch.setattr(api_mod, "open_in_browser", lambda url, b, is_default: opened.append((b, is_default)))
    monkeypatch.setattr(api_mod.time, "sleep", lambda s: None)

    class FakeYTM:
        def login(self, headers):
            assert "authorization: SAPISIDHASH" in headers
            return {"name": "Me"}

    class FakeApp:
        bus, ytm = EventBus(), FakeYTM()
        resolver = type("R", (), {"clear": lambda self: None})()
        viewer_running = staticmethod(lambda: False)

    app = FakeApp()
    events = []
    app.bus.listen(lambda kind, data: events.append((kind, data)))
    a = api_mod.Api(app)
    assert a.rpc_login_start() == {"status": "waiting", "browser": "Brave"}
    assert opened == [("brave", True)]
    for _ in range(200):
        if ("login", {"status": "signed-in", "name": "Me"}) in events:
            break
        time.sleep(0.01)
    assert calls["n"] == 3 and ("login", {"status": "signed-in", "name": "Me"}) in events


# ---------------------------------------------------------------- search & streams
def test_parse_count():
    assert models.parse_count("7B") == 7_000_000_000
    assert models.parse_count("1.2M") == 1_200_000
    assert models.parse_count("155K") == 155_000
    assert models.parse_count("1,234") == 1234
    assert models.parse_count(None) is None and models.parse_count("n/a") is None


def test_search_ranks_matching_songs_by_popularity():
    items = [dict(song("a"), title="Believer (Live)", views=155_000), dict(song("b"), title="Believe", views=799_000_000),
             dict(song("c"), title="Believer", views=7_000_000_000), dict(song("d"), title="Believer remix")]
    assert [t["videoId"] for t in models.rank_by_popularity(items, "believer")] == ["c", "a", "d", "b"]


def test_fast_path_uses_a_client_yt_dlp_supports():
    from yt_dlp.extractor.youtube._base import INNERTUBE_CLIENTS
    from cleftune.streams import fast_path_client
    assert fast_path_client() in INNERTUBE_CLIENTS
