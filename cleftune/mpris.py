"""MPRIS2 on the session D-Bus: media keys and desktop media widgets on Linux."""

# No `from __future__ import annotations` here: dbus-next reads D-Bus signatures from the annotations.
import asyncio
import threading

try:
    from dbus_next import Variant
    from dbus_next.aio import MessageBus
    from dbus_next.constants import PropertyAccess
    from dbus_next.service import ServiceInterface, dbus_property, method, signal
except ImportError:  # optional dependency
    ServiceInterface = None

from . import APP_ID, APP_NAME

BUS_NAME = f"org.mpris.MediaPlayer2.{APP_ID}"
OBJECT_PATH = "/org/mpris/MediaPlayer2"


def start_mpris(player, bus_events, quit_callback, raise_callback=None):
    """Start the MPRIS service in a background thread. Returns False when unavailable."""
    if ServiceInterface is None:
        return False

    class Root(ServiceInterface):
        def __init__(self):
            super().__init__("org.mpris.MediaPlayer2")

        @method()
        def Raise(self):
            if raise_callback:
                raise_callback()

        @method()
        def Quit(self):
            quit_callback()

        @dbus_property(access=PropertyAccess.READ)
        def CanQuit(self) -> "b":
            return True

        @dbus_property(access=PropertyAccess.READ)
        def CanRaise(self) -> "b":
            return raise_callback is not None

        @dbus_property(access=PropertyAccess.READ)
        def HasTrackList(self) -> "b":
            return False

        @dbus_property(access=PropertyAccess.READ)
        def Identity(self) -> "s":
            return APP_NAME

        @dbus_property(access=PropertyAccess.READ)
        def DesktopEntry(self) -> "s":
            return APP_ID

        @dbus_property(access=PropertyAccess.READ)
        def SupportedUriSchemes(self) -> "as":
            return []

        @dbus_property(access=PropertyAccess.READ)
        def SupportedMimeTypes(self) -> "as":
            return []

    class Player(ServiceInterface):
        def __init__(self):
            super().__init__("org.mpris.MediaPlayer2.Player")

        @staticmethod
        def _track_id():
            cur = player.current
            safe = "".join(c if c.isalnum() else "_" for c in (cur or {}).get("videoId", "none"))
            return f"/org/mpris/MediaPlayer2/track/{safe}"

        @method()
        def Next(self):
            player.next()

        @method()
        def Previous(self):
            player.previous()

        @method()
        def Pause(self):
            player.pause()

        @method()
        def PlayPause(self):
            player.toggle()

        @method()
        def Stop(self):
            player.stop()

        @method()
        def Play(self):
            player.play()

        @method()
        def Seek(self, offset: "x"):
            player.seek(player.pos + offset / 1_000_000)

        @method()
        def SetPosition(self, track_id: "o", position: "x"):
            if track_id == self._track_id():
                player.seek(position / 1_000_000)

        @method()
        def OpenUri(self, uri: "s"):
            pass

        @signal()
        def Seeked(self) -> "x":
            return int(player.pos * 1_000_000)

        @dbus_property(access=PropertyAccess.READ)
        def PlaybackStatus(self) -> "s":
            state = player.state()
            if state["playing"]:
                return "Playing"
            return "Paused" if state["current"] else "Stopped"

        @dbus_property(access=PropertyAccess.READ)
        def LoopStatus(self) -> "s":
            return {"off": "None", "all": "Playlist", "one": "Track"}[player.repeat]

        @dbus_property(access=PropertyAccess.READ)
        def Rate(self) -> "d":
            return 1.0

        @dbus_property(access=PropertyAccess.READ)
        def Shuffle(self) -> "b":
            return player.shuffle

        @dbus_property(access=PropertyAccess.READ)
        def Metadata(self) -> "a{sv}":
            cur = player.current
            if not cur:
                return {"mpris:trackid": Variant("o", "/org/mpris/MediaPlayer2/TrackList/NoTrack")}
            meta = {
                "mpris:trackid": Variant("o", self._track_id()),
                "xesam:title": Variant("s", cur.get("title") or ""),
                "xesam:artist": Variant("as", [a["name"] for a in cur.get("artists") or []] or [""]),
                "xesam:url": Variant("s", f"https://music.youtube.com/watch?v={cur['videoId']}"),
            }
            if cur.get("album"):
                meta["xesam:album"] = Variant("s", cur["album"].get("name") or "")
            if cur.get("thumbnail"):
                meta["mpris:artUrl"] = Variant("s", cur["thumbnail"])
            length = player.duration or cur.get("duration")
            if length:
                meta["mpris:length"] = Variant("x", int(length * 1_000_000))
            return meta

        @dbus_property(access=PropertyAccess.READ)
        def Volume(self) -> "d":
            return player.volume / 100

        @dbus_property(access=PropertyAccess.READ)
        def Position(self) -> "x":
            return int(player.pos * 1_000_000)

        @dbus_property(access=PropertyAccess.READ)
        def MinimumRate(self) -> "d":
            return 1.0

        @dbus_property(access=PropertyAccess.READ)
        def MaximumRate(self) -> "d":
            return 1.0

        @dbus_property(access=PropertyAccess.READ)
        def CanGoNext(self) -> "b":
            return True

        @dbus_property(access=PropertyAccess.READ)
        def CanGoPrevious(self) -> "b":
            return True

        @dbus_property(access=PropertyAccess.READ)
        def CanPlay(self) -> "b":
            return player.current is not None

        @dbus_property(access=PropertyAccess.READ)
        def CanPause(self) -> "b":
            return True

        @dbus_property(access=PropertyAccess.READ)
        def CanSeek(self) -> "b":
            return True

        @dbus_property(access=PropertyAccess.READ)
        def CanControl(self) -> "b":
            return True

    ready = threading.Event()
    result = {"ok": False}

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        iface = Player()
        last = {}

        async def setup():
            bus = await MessageBus().connect()
            bus.export(OBJECT_PATH, Root())
            bus.export(OBJECT_PATH, iface)
            await bus.request_name(BUS_NAME)

        try:
            loop.run_until_complete(setup())
            result["ok"] = True
        except Exception:
            ready.set()
            return
        ready.set()

        def changed():
            state = player.state()
            snapshot = {
                "PlaybackStatus": iface.PlaybackStatus, "Metadata": (state["current"] or {}).get("videoId"),
                "LoopStatus": iface.LoopStatus, "Shuffle": player.shuffle, "Volume": player.volume,
                "Duration": round(player.duration or 0),
            }
            diff = {k: v for k, v in snapshot.items() if last.get(k) != v}
            last.update(snapshot)
            props = {}
            for key in diff:
                if key == "Duration":
                    props["Metadata"] = iface.Metadata
                elif key == "Metadata":
                    props["Metadata"] = iface.Metadata
                elif key == "Volume":
                    props["Volume"] = iface.Volume
                else:
                    props[key] = getattr(iface, key)
            if props:
                iface.emit_properties_changed(props)

        def on_event(kind, data):
            if kind == "state":
                loop.call_soon_threadsafe(changed)

        bus_events.listen(on_event)
        loop.run_forever()

    threading.Thread(target=run, name="mpris", daemon=True).start()
    ready.wait(timeout=5)
    return result["ok"]
