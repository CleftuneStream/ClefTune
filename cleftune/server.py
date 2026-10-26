"""Loopback HTTP server: serves the UI, a JSON RPC API, Server-Sent Events, and the audio relay."""

from __future__ import annotations

import json
import mimetypes
import queue
import re
import secrets
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .streams import StreamError, open_range

WEB_DIR = Path(__file__).parent / "web"
RELAY_CHUNK = 1024 * 1024          # bytes per upstream request; small ranges avoid YouTube throttling
_RANGE = re.compile(r"bytes=(\d*)-(\d*)")
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{6,20}$")


class RpcError(Exception):
    pass


class Server:
    def __init__(self, api, resolver, bus, port: int = 0):
        self.api, self.resolver, self.bus = api, resolver, bus
        self.token = secrets.token_urlsafe(24)
        handler = type("Handler", (_Handler,), {"app": self})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.allowed_hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}

    def start(self) -> None:
        threading.Thread(target=self.httpd.serve_forever, name="http", daemon=True).start()

    def stop(self) -> None:
        self.httpd.shutdown()

    def stream_path(self, video_id: str, gen: int) -> str:
        return f"/api/stream/{video_id}?g={gen}&token={self.token}"


class _Handler(BaseHTTPRequestHandler):
    app: Server
    protocol_version = "HTTP/1.1"
    server_version = "ClefTune"

    def log_message(self, fmt, *args):  # keep the console quiet
        pass

    # -- guards -----------------------------------------------------------
    def _host_ok(self) -> bool:
        # blocks DNS-rebinding: a hostile site resolving its name to 127.0.0.1 sends its own Host header
        return self.headers.get("Host", "") in self.app.allowed_hosts

    def _token_ok(self, query: dict) -> bool:
        given = self.headers.get("X-Token") or (query.get("token") or [""])[0]
        return secrets.compare_digest(given, self.app.token)

    def _send(self, status: int, body: bytes, content_type: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json")

    # -- routing ----------------------------------------------------------
    def do_GET(self):
        if not self._host_ok():
            return self._send(403, b"Forbidden", "text/plain")
        url = urlparse(self.path)
        query = parse_qs(url.query)
        path = url.path
        if path in ("/", "/index.html"):
            return self._index()
        if path.startswith("/static/"):
            return self._static(path[len("/static/"):])
        if not self._token_ok(query):
            return self._send(401, b"Unauthorized", "text/plain")
        if path == "/api/events":
            return self._events()
        if path.startswith("/api/stream/"):
            return self._stream(path.rsplit("/", 1)[-1])
        self._send(404, b"Not found", "text/plain")

    do_HEAD = do_GET

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, b"Forbidden", "text/plain")
        url = urlparse(self.path)
        if not self._token_ok(parse_qs(url.query)):
            return self._send(401, b"Unauthorized", "text/plain")
        if not url.path.startswith("/api/call/"):
            return self._send(404, b"Not found", "text/plain")
        name = url.path[len("/api/call/"):]
        length = int(self.headers.get("Content-Length") or 0)
        try:
            params = json.loads(self.rfile.read(length) or b"{}") if length else {}
            fn = getattr(self.app.api, f"rpc_{name}", None)
            if fn is None:
                raise RpcError(f"Unknown method {name}")
            result = fn(**params)
            self._json(200, {"ok": True, "result": result})
        except (RpcError, ValueError, KeyError, TypeError) as exc:
            self._json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # network errors from YouTube etc.
            self._json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    # -- UI ---------------------------------------------------------------
    def _index(self):
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        html = html.replace("__TOKEN__", self.app.token)
        self._send(200, html.encode(), "text/html; charset=utf-8",
                   {"Content-Security-Policy": "default-src 'self'; img-src * data: blob:; "
                                               "media-src 'self' blob:; style-src 'self' 'unsafe-inline'; "
                                               "script-src 'self'; connect-src 'self'"})

    def _static(self, name: str):
        target = (WEB_DIR / name).resolve()
        if WEB_DIR.resolve() not in target.parents or not target.is_file():
            return self._send(404, b"Not found", "text/plain")
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix == ".js":
            ctype = "text/javascript"
        self._send(200, target.read_bytes(), ctype)

    def _events(self):
        q = self.app.bus.subscribe()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write(b"retry: 1500\n\n")
            self.wfile.flush()
            while True:
                try:
                    kind, payload = q.get(timeout=15)
                    self.wfile.write(f"event: {kind}\ndata: {payload}\n\n".encode())
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.app.bus.unsubscribe(q)

    # -- audio relay ------------------------------------------------------
    def _stream(self, video_id: str):
        if not _VIDEO_ID.match(video_id):
            return self._send(400, b"Bad id", "text/plain")
        self.close_connection = True
        try:
            info = self.app.resolver.resolve(video_id)
        except Exception as exc:
            return self._send(502, str(exc).encode(), "text/plain")
        start, end = 0, None
        range_header = self.headers.get("Range")
        if range_header:
            m = _RANGE.match(range_header.strip())
            if m and m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else None
        if info.path:
            return self._relay_file(info, start, end, bool(range_header))
        self._relay_remote(video_id, info, start, end, bool(range_header))

    def _relay_file(self, info, start: int, end: int | None, ranged: bool):
        total = info.size
        if start >= total:
            return self._send(416, b"", "text/plain", {"Content-Range": f"bytes */{total}"})
        end = min(end if end is not None else total - 1, total - 1)
        self._begin_body(info.mime, start, end, total, ranged)
        if self.command == "HEAD":
            return
        try:
            with open(info.path, "rb") as fh:
                fh.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk = fh.read(min(256 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _begin_body(self, mime: str, start: int, end: int, total: int, ranged: bool):
        self.send_response(206 if ranged else 200)
        self.send_header("Content-Type", mime)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", "no-store")
        if ranged:
            self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
        self.end_headers()

    def _relay_remote(self, video_id: str, info, start: int, end: int | None, ranged: bool):
        head = self.app.resolver.get_head(video_id, wait=6.0)
        if head and start < len(head.data):
            # pre-downloaded start of the song: playback begins without waiting on YouTube
            total = head.total
            end = min(end if end is not None else total - 1, total - 1)
            self._begin_body(info.mime, start, end, total, ranged)
            if self.command == "HEAD":
                return
            try:
                self.wfile.write(head.data[start:min(len(head.data), end + 1)])
                if len(head.data) <= end:
                    self._pump(video_id, info, len(head.data), end, None)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        try:
            first_last = start + RELAY_CHUNK - 1 if end is None else min(end, start + RELAY_CHUNK - 1)
            info, resp = open_range(self.app.resolver, video_id, info, start, first_last)
        except urllib.error.HTTPError as exc:
            if exc.code == 416:
                return self._send(416, b"", "text/plain")
            return self._send(502, f"Upstream error {exc.code}".encode(), "text/plain")
        except (OSError, StreamError) as exc:
            return self._send(502, f"Upstream error: {exc}".encode(), "text/plain")
        total = None
        content_range = resp.headers.get("Content-Range", "")
        if "/" in content_range:
            tail = content_range.rsplit("/", 1)[1]
            total = int(tail) if tail.isdigit() else None
        total = total or info.size
        if not total:
            resp.close()
            return self._send(502, b"Unknown stream length", "text/plain")
        end = min(end if end is not None else total - 1, total - 1)
        self._begin_body(info.mime, start, end, total, ranged)
        if self.command == "HEAD":
            resp.close()
            return
        try:
            self._pump(video_id, info, start, end, resp)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _pump(self, video_id: str, info, pos: int, end: int, resp) -> None:
        """Copy bytes pos..end to the client in RELAY_CHUNK upstream requests."""
        try:
            while pos <= end:
                if resp is None:
                    info, resp = open_range(self.app.resolver, video_id, info, pos, min(end, pos + RELAY_CHUNK - 1))
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    pos += len(chunk)
                resp.close()
                resp = None
        except (BrokenPipeError, ConnectionResetError):
            raise
        except (OSError, StreamError):
            self.close_connection = True
        finally:
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass
