#!/usr/bin/env python3
"""Hermes in Chrome: the local bridge between an AI agent and the browser extension.

One long-lived process with two faces, both on the loopback interface only:

* ``POST /mcp`` is an MCP server (streamable HTTP, JSON responses). The agent connects here.
  Every agent process shares this one endpoint, so nothing is started per session.
* ``GET /ext`` is a WebSocket held open by the Hermes in Chrome extension. Tool calls are
  forwarded over it and answered by the extension, which works only in its own tab.

Standard library only (Python 3.9 or newer), so there is nothing to install and nothing to keep
up to date.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import logging
import os
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional

__version__ = "0.1.0"

HOST = "127.0.0.1"
DEFAULT_PORT = 8790
DEFAULT_IDLE_CLOSE_SECONDS = 600
COMMAND_TIMEOUT_SECONDS = 45
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
SERVER_INFO = {"name": "hermes-in-chrome", "version": __version__}
DEFAULT_PROTOCOL = "2025-06-18"

log = logging.getLogger("hermes-in-chrome")

NOT_CONNECTED = (
    "The Hermes in Chrome extension is not connected. Chrome may be closed, or the extension is "
    "not installed or is switched off (chrome://extensions). Tell the user; do not try another "
    "way into their browser."
)


def _schema(properties: Dict[str, Any], required: Optional[List[str]] = None) -> Dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}


_REF = {"type": "integer", "description": "Element ref from the latest `read` of the page."}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "open",
        "description": (
            "Load a URL in your working tab in the user's own Chrome. The tab lives in its own tab "
            "group; it is created on first use and reused afterwards, so there is only ever one. "
            "It opens in the background: the user keeps working in their own tabs, which you "
            "cannot see or touch. Returns the page title and final URL; call `read` to see content."
        ),
        "inputSchema": _schema({"url": {"type": "string", "description": "Absolute http(s) URL."}}, ["url"]),
    },
    {
        "name": "read",
        "description": (
            "Read the working tab: title, URL, the visible page text, and a numbered list of "
            "interactive elements (links, buttons, inputs) whose `ref` you pass to click, type and "
            "hover. Refs are only valid until the page changes; read again after navigating or "
            "clicking."
        ),
        "inputSchema": _schema({
            "max_chars": {"type": "integer", "description": "Cap on page text returned. Default 6000."},
            "filter": {"type": "string", "description": "Only list elements whose label contains this text."},
        }),
    },
    {
        "name": "click",
        "description": "Click an element in the working tab by its ref. Returns the page title and URL afterwards.",
        "inputSchema": _schema({"ref": _REF}, ["ref"]),
    },
    {
        "name": "type",
        "description": (
            "Type text into an input, textarea, dropdown or editable element by its ref, replacing "
            "its current value. Password fields are refused."
        ),
        "inputSchema": _schema({
            "ref": _REF,
            "text": {"type": "string"},
            "submit": {"type": "boolean", "description": "Press Enter afterwards (submits most search boxes and forms)."},
        }, ["ref", "text"]),
    },
    {
        "name": "press_key",
        "description": (
            "Press a key in the working tab, sent to the focused element: Enter, Escape, Tab, "
            "Space, Backspace, ArrowDown, ArrowUp, ArrowLeft, ArrowRight, PageDown, PageUp."
        ),
        "inputSchema": _schema({"key": {"type": "string"}}, ["key"]),
    },
    {
        "name": "scroll",
        "description": (
            "Scroll the working tab (the page, or its main inner panel on app-style layouts). Use it "
            "to load lazy content or reach elements further down, then read again. The result says "
            "how far it moved; if it reports 0 and content is still missing, call `show` and scroll "
            "with a screen-control tool if you have one."
        ),
        "inputSchema": _schema({
            "direction": {"type": "string", "enum": ["down", "up", "top", "bottom"]},
            "pages": {"type": "number", "description": "How many screenfuls for up/down. Default 1."},
        }, ["direction"]),
    },
    {
        "name": "hover",
        "description": (
            "Move the pointer over an element in the working tab by its ref, to reveal a menu or a "
            "tooltip that is part of the page. Read again afterwards. Tooltips drawn inside a canvas "
            "chart are pixels and will not appear in the text."
        ),
        "inputSchema": _schema({"ref": _REF}, ["ref"]),
    },
    {
        "name": "show",
        "description": (
            "Bring your working tab to the front of the user's Chrome window. Call this before "
            "using a screen-control tool (computer use) on it, which is the way to handle what the "
            "page tools cannot: values drawn in a canvas chart or shown only on hover, a page that "
            "will not scroll, drag gestures, or a click that has no effect twice. It takes over "
            "what the user sees, so say that you are doing it."
        ),
        "inputSchema": _schema({}),
    },
    {
        "name": "back",
        "description": "Go back one page in the working tab's history.",
        "inputSchema": _schema({}),
    },
    {
        "name": "close",
        "description": "Close your working tab. Do this when the task is finished, unless the user asked to keep the page open.",
        "inputSchema": _schema({}),
    },
    {
        "name": "status",
        "description": "Whether the Chrome extension is connected and what your working tab currently shows.",
        "inputSchema": _schema({}),
    },
]
TOOL_NAMES = {tool["name"] for tool in TOOLS}


class Extension:
    """The single connected extension and the commands waiting on it."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._socket = None
        self._pending: Dict[int, Dict[str, Any]] = {}
        self._next_id = 0
        self.last_command_at = 0.0
        self.tab_open = False

    @property
    def connected(self) -> bool:
        return self._socket is not None

    def attach(self, sock) -> None:
        with self._lock:
            previous, self._socket = self._socket, sock
        if previous is not None:
            # shutdown, not just close: the old connection's thread is blocked reading, and close
            # alone would leave the connection open, so that extension would never learn it had
            # been replaced and would never dial again.
            try:
                previous.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                previous.close()
            except OSError:
                pass

    def detach(self, sock) -> None:
        with self._lock:
            if self._socket is sock:
                self._socket = None
            waiting = list(self._pending.values()) if self._socket is None else []
        for entry in waiting:
            entry["response"] = {"ok": False, "error": "The extension disconnected before answering."}
            entry["event"].set()

    def send_raw(self, sock, frame: bytes) -> None:
        with self._send_lock:
            sock.sendall(frame)

    def send_text(self, sock, payload: str) -> None:
        data = payload.encode("utf-8")
        header = bytearray([0x81])
        if len(data) < 126:
            header.append(len(data))
        elif len(data) < 65536:
            header.append(126)
            header += struct.pack(">H", len(data))
        else:
            header.append(127)
            header += struct.pack(">Q", len(data))
        self.send_raw(sock, bytes(header) + data)

    def resolve(self, message: Dict[str, Any]) -> None:
        with self._lock:
            entry = self._pending.pop(message.get("id"), None)
        if entry is not None:
            entry["response"] = message
            entry["event"].set()

    def command(self, name: str, args: Dict[str, Any], timeout: float = COMMAND_TIMEOUT_SECONDS) -> Dict[str, Any]:
        with self._lock:
            sock = self._socket
            if sock is None:
                return {"ok": False, "error": NOT_CONNECTED}
            self._next_id += 1
            command_id = self._next_id
            entry: Dict[str, Any] = {"event": threading.Event(), "response": None}
            self._pending[command_id] = entry
        try:
            self.send_text(sock, json.dumps({"id": command_id, "command": name, "args": args}))
        except OSError:
            self.detach(sock)
            return {"ok": False, "error": NOT_CONNECTED}
        if not entry["event"].wait(timeout):
            with self._lock:
                self._pending.pop(command_id, None)
            return {"ok": False, "error": f"Chrome did not answer `{name}` within {int(timeout)} seconds."}
        return entry["response"] or {"ok": False, "error": "Empty answer from the extension."}


class Bridge:
    """Settings and state shared by every request."""

    def __init__(self, idle_close_seconds: int = DEFAULT_IDLE_CLOSE_SECONDS,
                 extension_ids: Optional[List[str]] = None, token: str = "") -> None:
        self.extension = Extension()
        self.idle_close_seconds = idle_close_seconds
        self.extension_ids = {item.strip() for item in (extension_ids or []) if item.strip()}
        self.token = token

    def extension_allowed(self, origin: str) -> bool:
        prefix = "chrome-extension://"
        if not origin.startswith(prefix):
            return False
        return not self.extension_ids or origin[len(prefix):].strip("/") in self.extension_ids

    def call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name not in TOOL_NAMES:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        response = self.extension.command(name, args)
        if response.get("ok") and name != "status":
            self.extension.last_command_at = time.time()
            self.extension.tab_open = name != "close"
        return response

    def close_idle_tab(self) -> bool:
        """Close the working tab once the agent has left it alone long enough, so a finished task
        never leaves a tab behind even if the model forgets to close it."""
        extension = self.extension
        if self.idle_close_seconds <= 0 or not (extension.tab_open and extension.connected):
            return False
        if time.time() - extension.last_command_at < self.idle_close_seconds:
            return False
        log.info("working tab idle for %ss: closing it", self.idle_close_seconds)
        extension.command("close", {"reason": "idle"}, timeout=10)
        extension.tab_open = False
        return True

    def sweep_forever(self, interval: float = 30.0) -> None:
        while True:
            time.sleep(interval)
            self.close_idle_tab()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "HermesInChrome/" + __version__

    @property
    def bridge(self) -> Bridge:
        return self.server.bridge  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:  # request lines are noise
        return

    # ── guards ───────────────────────────────────────────────────────────────────────────────

    def _local_host(self) -> bool:
        """Reject requests addressed to any other name (DNS rebinding)."""
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in {"127.0.0.1", "localhost"}

    def _from_web_page(self) -> bool:
        """A browser always sends Origin on a cross-origin POST. An agent sends none, so any
        Origin here is a web page trying to drive the user's browser through this port."""
        return bool(self.headers.get("Origin"))

    def _authorised(self) -> bool:
        token = self.bridge.token
        if not token:
            return True
        supplied = self.headers.get("Authorization") or ""
        return hmac.compare_digest(supplied, f"Bearer {token}")

    def _json(self, status: int, body: Any) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _empty(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ── HTTP ─────────────────────────────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        if not self._local_host():
            return self._empty(403)
        if self.path == "/ext":
            return self._websocket()
        if self.path == "/health":
            return self._json(200, {"ok": True, "extension_connected": self.bridge.extension.connected, **SERVER_INFO})
        # /mcp has no server-initiated stream.
        self._empty(405)

    def do_DELETE(self) -> None:
        self._empty(200 if self.path == "/mcp" else 404)

    def do_POST(self) -> None:
        if self.path not in ("/mcp", "/admin/reload-extension"):
            return self._empty(404)
        if not self._local_host() or self._from_web_page():
            return self._empty(403)
        if not self._authorised():
            return self._empty(401)
        if self.path == "/admin/reload-extension":
            # Maintenance: makes the extension re-read its files from disk after an edit.
            return self._json(200, self.bridge.extension.command("_reload", {}, timeout=10))
        try:
            length = int(self.headers.get("Content-Length") or 0)
            message = json.loads(self.rfile.read(length) or b"null")
        except ValueError:
            return self._json(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})

        if isinstance(message, list):
            replies = [reply for reply in (self._rpc(item) for item in message) if reply is not None]
            return self._json(200, replies) if replies else self._empty(202)
        reply = self._rpc(message)
        if reply is None:
            return self._empty(202)
        self._json(200, reply)

    def _rpc(self, message: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(message, dict):
            return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
        method, request_id = message.get("method"), message.get("id")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        if request_id is None:
            return None  # a notification

        def ok(result: Any) -> Dict[str, Any]:
            return {"jsonrpc": "2.0", "id": request_id, "result": result}

        if method == "initialize":
            return ok({
                "protocolVersion": params.get("protocolVersion") or DEFAULT_PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": (
                    "Drives one working tab, in its own tab group, in the user's own Chrome. "
                    "You cannot see or touch the user's other tabs."
                ),
            })
        if method == "ping":
            return ok({})
        if method == "tools/list":
            return ok({"tools": TOOLS})
        if method == "tools/call":
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            response = self.bridge.call_tool(str(params.get("name") or ""), arguments)
            if response.get("ok"):
                text = json.dumps(response.get("result"), ensure_ascii=False)
                return ok({"content": [{"type": "text", "text": text}], "isError": False})
            return ok({"content": [{"type": "text", "text": str(response.get("error") or "Failed")}], "isError": True})
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}

    # ── WebSocket (the extension) ────────────────────────────────────────────────────────────

    def _websocket(self) -> None:
        key = self.headers.get("Sec-WebSocket-Key")
        origin = self.headers.get("Origin") or ""
        if (self.headers.get("Upgrade") or "").lower() != "websocket" or not key:
            return self._empty(400)
        if not self.bridge.extension_allowed(origin):
            return self._empty(403)
        accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        self.close_connection = True

        sock = self.connection
        sock.settimeout(90)  # the extension pings every 20 s; silence this long means it is gone
        extension = self.bridge.extension
        extension.attach(sock)
        log.info("extension connected (%s)", origin)
        try:
            self._read_frames(sock, extension)
        except (OSError, ValueError) as exc:
            log.info("extension connection ended: %s", exc)
        finally:
            extension.detach(sock)
            log.info("extension disconnected")

    def _read_exact(self, count: int) -> bytes:
        data = self.rfile.read(count)
        if len(data) != count:
            raise OSError("socket closed")
        return data

    def _read_frames(self, sock, extension: Extension) -> None:
        fragments = b""
        while True:
            first, second = self._read_exact(2)
            opcode, final = first & 0x0F, bool(first & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read_exact(8))[0]
            mask = self._read_exact(4) if second & 0x80 else b""
            payload = self._read_exact(length)
            if mask:
                payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
            if opcode == 0x8:  # close
                return
            if opcode == 0x9:  # ping
                extension.send_raw(sock, bytes([0x8A, len(payload)]) + payload)
                continue
            if opcode == 0xA:  # pong
                continue
            fragments += payload
            if not final:
                continue
            text, fragments = fragments.decode("utf-8", "replace"), b""
            try:
                message = json.loads(text)
            except ValueError:
                continue
            if isinstance(message, dict) and "id" in message:
                extension.resolve(message)


def build_server(port: int = DEFAULT_PORT, bridge: Optional[Bridge] = None) -> ThreadingHTTPServer:
    """A server bound to the loopback interface. ``port=0`` picks a free port (used by the tests)."""
    server = ThreadingHTTPServer((HOST, port), Handler)
    server.daemon_threads = True
    server.bridge = bridge or Bridge()  # type: ignore[attr-defined]
    return server


def main(argv: Optional[List[str]] = None) -> None:
    env = os.environ
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, default=int(env.get("HERMES_IN_CHROME_PORT", DEFAULT_PORT)),
                        help=f"Port on 127.0.0.1 (default {DEFAULT_PORT}).")
    parser.add_argument("--idle-close-seconds", type=int,
                        default=int(env.get("HERMES_IN_CHROME_IDLE_CLOSE_SECONDS", DEFAULT_IDLE_CLOSE_SECONDS)),
                        help="Close the working tab after this long without a command. 0 never closes it.")
    parser.add_argument("--extension-id", action="append", default=[],
                        help="Only accept this extension ID (repeatable). Default accepts any extension.")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    extension_ids = args.extension_id or [item for item in env.get("HERMES_IN_CHROME_EXTENSION_IDS", "").split(",") if item]
    bridge = Bridge(args.idle_close_seconds, extension_ids, env.get("HERMES_IN_CHROME_TOKEN", ""))

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    threading.Thread(target=bridge.sweep_forever, daemon=True).start()
    server = build_server(args.port, bridge)
    log.info("listening on http://%s:%s (agent: /mcp, extension: /ext)%s", HOST, server.server_address[1],
             ", token required" if bridge.token else "")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
