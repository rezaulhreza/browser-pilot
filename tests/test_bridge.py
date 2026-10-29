"""Tests for the bridge, run against a real server on a free loopback port.

The browser extension is replaced by a small WebSocket client that answers commands the way the
extension would, so the whole path from an MCP request to the extension and back is exercised.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import struct
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bridge"))

import bridge as bridge_module  # noqa: E402

EXTENSION_ORIGIN = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"


class FakeExtension:
    """A WebSocket client that plays the extension: it answers every command it is sent."""

    def __init__(self, port: int, origin: str = EXTENSION_ORIGIN, answer=None, host: str = "") -> None:
        self.answer = answer or (lambda command, args: {"ok": True, "result": {"echo": command, "args": args}})
        self.commands = []
        self.dropped = threading.Event()  # set once the server has hung up on this client
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((
            f"GET /ext HTTP/1.1\r\nHost: {host or f'127.0.0.1:{port}'}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nOrigin: {origin}\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(1024)
            if not chunk:
                break
            head += chunk
        self.status = int(head.split(b" ", 2)[1]) if head else 0
        if self.status == 101:
            threading.Thread(target=self._serve, daemon=True).start()

    def _read(self, count: int) -> bytes:
        data = b""
        while len(data) < count:
            chunk = self.sock.recv(count - len(data))
            if not chunk:
                raise OSError("closed")
            data += chunk
        return data

    def _serve(self) -> None:
        try:
            while True:
                _first, second = self._read(2)
                length = second & 0x7F
                if length == 126:
                    length = struct.unpack(">H", self._read(2))[0]
                elif length == 127:
                    length = struct.unpack(">Q", self._read(8))[0]
                message = json.loads(self._read(length).decode())
                self.commands.append(message["command"])
                self.send({"id": message["id"], **self.answer(message["command"], message["args"])})
        except (OSError, ValueError):
            pass
        finally:
            self.dropped.set()

    def send(self, payload: dict) -> None:
        data = json.dumps(payload).encode()
        mask = os.urandom(4)
        header = bytearray([0x81])
        if len(data) < 126:
            header.append(0x80 | len(data))
        elif len(data) < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", len(data))
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", len(data))
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        self.sock.sendall(bytes(header) + mask + masked)

    def close(self) -> None:
        # shutdown (unlike close) sends FIN at once and wakes the server's blocked read, so the
        # bridge notices the disconnection promptly rather than waiting out the socket timeout.
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


class BridgeTestCase(unittest.TestCase):
    token = ""
    extension_ids = None
    idle_close_seconds = 600
    allowed_hosts = None

    def setUp(self) -> None:
        self.bridge = bridge_module.Bridge(self.idle_close_seconds, self.extension_ids, self.token,
                                           self.allowed_hosts)
        self.server = bridge_module.build_server(0, self.bridge)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def post(self, body, headers=None, path="/mcp"):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            return error.code, None

    def call(self, name, **arguments):
        _status, reply = self.post({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                    "params": {"name": name, "arguments": arguments}})
        result = reply["result"]
        return result["isError"], result["content"][0]["text"]

    def connect(self, **kwargs) -> FakeExtension:
        extension = FakeExtension(self.port, **kwargs)
        self.addCleanup(extension.close)
        if extension.status == 101:
            deadline = time.time() + 2
            while not self.bridge.extension.connected and time.time() < deadline:
                time.sleep(0.01)
        return extension


class McpProtocolTest(BridgeTestCase):
    def test_initialize_echoes_the_clients_protocol_version(self):
        status, reply = self.post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                   "params": {"protocolVersion": "2024-11-05"}})
        self.assertEqual(status, 200)
        self.assertEqual(reply["result"]["protocolVersion"], "2024-11-05")
        self.assertIn("tools", reply["result"]["capabilities"])

    def test_notifications_are_accepted_without_a_body(self):
        status, reply = self.post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual((status, reply), (202, None))

    def test_every_listed_tool_has_a_schema_that_forbids_unknown_arguments(self):
        _status, reply = self.post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = reply["result"]["tools"]
        self.assertEqual({tool["name"] for tool in tools}, bridge_module.TOOL_NAMES)
        for tool in tools:
            self.assertIs(tool["inputSchema"]["additionalProperties"], False, tool["name"])
            self.assertTrue(set(tool["inputSchema"]["required"]) <= set(tool["inputSchema"]["properties"]))

    def test_every_tool_that_works_in_a_tab_may_name_the_tab(self):
        _status, reply = self.post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = {tool["name"]: tool for tool in reply["result"]["tools"]}
        self.assertTrue({"tabs_context", "tabs_create"} <= set(tools))
        for name in ("open", "act", "read", "click", "type", "press_key", "scroll", "hover", "show", "back", "close"):
            self.assertEqual(tools[name]["inputSchema"]["properties"]["tab_id"]["type"], "integer", name)
        for name in ("tabs_context", "tabs_create", "status"):
            self.assertNotIn("tab_id", tools[name]["inputSchema"]["properties"], name)

    def test_the_tools_that_start_work_may_name_the_task(self):
        _status, reply = self.post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        named = {tool["name"] for tool in reply["result"]["tools"] if "task" in tool["inputSchema"]["properties"]}
        self.assertEqual(named, {"open", "act", "tabs_create"})

    def test_the_task_reaches_the_extension(self):
        extension = self.connect(answer=lambda command, args: {"ok": True, "result": args})
        _is_error, text = self.call("open", url="https://example.com", task="Comparing flight prices")
        self.assertEqual(json.loads(text)["task"], "Comparing flight prices")
        self.assertEqual(extension.commands, ["open"])

    def test_unknown_method_is_a_json_rpc_error(self):
        _status, reply = self.post({"jsonrpc": "2.0", "id": 7, "method": "resources/list"})
        self.assertEqual(reply["error"]["code"], -32601)
        self.assertEqual(reply["id"], 7)


class ToolCallTest(BridgeTestCase):
    def test_without_the_extension_a_call_explains_what_is_wrong(self):
        is_error, text = self.call("status")
        self.assertTrue(is_error)
        self.assertIn("not connected", text)

    def test_a_call_reaches_the_extension_and_its_answer_comes_back(self):
        extension = self.connect()
        is_error, text = self.call("open", url="https://example.com")
        self.assertFalse(is_error)
        self.assertEqual(json.loads(text), {"echo": "open", "args": {"url": "https://example.com"}})
        self.assertEqual(extension.commands, ["open"])

    def test_an_extension_error_is_reported_as_a_tool_error(self):
        self.connect(answer=lambda command, args: {"ok": False, "error": "That ref is no longer on the page."})
        self.assertEqual(self.call("click", ref=3), (True, "That ref is no longer on the page."))

    def test_a_large_page_survives_the_round_trip(self):
        page = "x" * 200_000
        self.connect(answer=lambda command, args: {"ok": True, "result": {"text": page}})
        is_error, text = self.call("read")
        self.assertFalse(is_error)
        self.assertEqual(json.loads(text)["text"], page)

    def test_unknown_tool_never_reaches_the_extension(self):
        extension = self.connect()
        is_error, _text = self.call("list_all_tabs")
        self.assertTrue(is_error)
        self.assertEqual(extension.commands, [])

    def test_parallel_calls_each_get_their_own_answer(self):
        self.connect()
        results = {}

        def run(name):
            results[name] = json.loads(self.call(name)[1])["echo"]

        threads = [threading.Thread(target=run, args=(name,)) for name in ("status", "back", "close", "read")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(results, {"status": "status", "back": "back", "close": "close", "read": "read"})

    def test_calls_fail_cleanly_once_the_extension_disconnects(self):
        extension = self.connect()
        extension.close()
        deadline = time.time() + 5
        while self.bridge.extension.connected and time.time() < deadline:
            time.sleep(0.01)
        self.assertFalse(self.bridge.extension.connected, "the bridge did not notice the extension disconnecting")
        is_error, text = self.call("read")
        self.assertTrue(is_error)
        self.assertIn("not connected", text)


class IdleTabTest(BridgeTestCase):
    idle_close_seconds = 1

    def test_a_tab_left_alone_is_closed(self):
        extension = self.connect()
        self.call("open", url="https://example.com")
        self.assertFalse(self.bridge.close_idle_tab(), "closed while still in use")
        self.bridge.extension.last_command_at -= 5
        self.assertTrue(self.bridge.close_idle_tab())
        self.assertEqual(extension.commands, ["open", "close"])
        self.assertFalse(self.bridge.close_idle_tab(), "closed twice")

    def test_a_tab_the_agent_closed_is_not_closed_again(self):
        extension = self.connect()
        self.call("open", url="https://example.com")
        self.call("close")
        self.bridge.extension.last_command_at -= 5
        self.assertFalse(self.bridge.close_idle_tab())
        self.assertEqual(extension.commands, ["open", "close"])

    def test_tabs_left_open_after_closing_one_are_still_closed_when_idle(self):
        extension = self.connect(answer=lambda command, args: {
            "ok": True, "result": {"closed": 1, "open_tabs": 1} if command == "close" else {}})
        self.call("open", url="https://example.com")
        self.call("tabs_create", url="https://example.org")
        self.call("close", tab_id=7)
        self.bridge.extension.last_command_at -= 5
        self.assertTrue(self.bridge.close_idle_tab())
        self.assertEqual(extension.commands, ["open", "tabs_create", "close", "close"])

    def test_listing_the_tabs_does_not_keep_them_open(self):
        extension = self.connect()
        self.call("open", url="https://example.com")
        self.bridge.extension.last_command_at -= 5
        self.call("tabs_context")
        self.assertTrue(self.bridge.close_idle_tab())
        self.assertEqual(extension.commands, ["open", "tabs_context", "close"])


class WebPageGuardTest(BridgeTestCase):
    """A page the user visits must not be able to drive their browser through this port."""

    def test_a_request_carrying_an_origin_is_refused(self):
        status, _reply = self.post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                                   headers={"Origin": "https://attacker.example"})
        self.assertEqual(status, 403)

    def test_a_request_for_another_host_name_is_refused(self):
        status, _reply = self.post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                                   headers={"Host": "attacker.example"})
        self.assertEqual(status, 403)

    def test_a_web_page_cannot_pose_as_the_extension(self):
        self.assertEqual(self.connect(origin="https://attacker.example").status, 403)
        self.assertFalse(self.bridge.extension.connected)


class ReplacedConnectionTest(BridgeTestCase):
    def test_a_replaced_connection_is_hung_up_and_the_new_one_gets_the_commands(self):
        """An extension whose connection was replaced must be told, or it goes on believing it
        is connected and never dials again."""
        first = self.connect()
        second = self.connect()
        self.assertTrue(first.dropped.wait(3), "the replaced connection was left open")
        is_error, _text = self.call("status")
        self.assertFalse(is_error)
        self.assertEqual((first.commands, second.commands), ([], ["status"]))


class PinnedExtensionTest(BridgeTestCase):
    extension_ids = ["abcdefghijklmnopabcdefghijklmnop"]

    def test_only_the_pinned_extension_may_connect(self):
        self.assertEqual(self.connect(origin="chrome-extension://someotherextensionidsomeotherext").status, 403)
        self.assertEqual(self.connect().status, 101)


class TokenTest(BridgeTestCase):
    token = "s3cret"

    def test_requests_need_the_token_when_one_is_set(self):
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        self.assertEqual(self.post(request)[0], 401)
        self.assertEqual(self.post(request, headers={"Authorization": "Bearer wrong"})[0], 401)
        self.assertEqual(self.post(request, headers={"Authorization": "Bearer s3cret"})[0], 200)


class ExtensionPortsTest(BridgeTestCase):
    """The maintenance route that tells the extension which bridges to connect to."""

    def test_a_list_of_ports_is_passed_to_the_extension(self):
        extension = self.connect()
        status, reply = self.post({"ports": [8790, 8791]}, path="/admin/extension-ports")
        self.assertEqual((status, reply["ok"]), (200, True))
        self.assertEqual(reply["result"], {"echo": "_ports", "args": {"ports": [8790, 8791]}})
        self.assertEqual(extension.commands, ["_ports"])

    def test_anything_that_is_not_a_short_list_of_ports_is_refused(self):
        extension = self.connect()
        for ports in ([], [0], [70000], ["8790"], [8790, 8790], [True], list(range(1, 10)), None, 8790):
            status, _reply = self.post({"ports": ports}, path="/admin/extension-ports")
            self.assertEqual(status, 400, ports)
        self.assertEqual(extension.commands, [])

    def test_a_web_page_and_another_host_name_cannot_use_it(self):
        for headers in ({"Origin": "https://attacker.example"}, {"Host": "attacker.example"}):
            status, _reply = self.post({"ports": [1]}, headers=headers, path="/admin/extension-ports")
            self.assertEqual(status, 403)


class AllowedHostTest(BridgeTestCase):
    """A tunnel or a container reaches the bridge by another name. Only a listed name gets in,
    only to the agent's route, and only with the password."""

    token = "s3cret"
    allowed_hosts = ["host.docker.internal", " Pilot.Example.com "]
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}

    def headers(self, host, token="s3cret"):
        return {"Host": host, "Authorization": f"Bearer {token}"}

    def test_each_listed_name_is_accepted_with_or_without_a_port(self):
        for host in ("host.docker.internal:8790", "pilot.example.com", "PILOT.example.com:443", "127.0.0.1"):
            self.assertEqual(self.post(self.request, headers=self.headers(host))[0], 200, host)

    def test_a_name_that_is_not_listed_is_still_refused(self):
        for host in ("attacker.example", "evil.host.docker.internal", "pilot.example.com.attacker.example"):
            self.assertEqual(self.post(self.request, headers=self.headers(host))[0], 403, host)

    def test_a_listed_name_still_needs_the_password(self):
        self.assertEqual(self.post(self.request, headers={"Host": "pilot.example.com"})[0], 401)
        self.assertEqual(self.post(self.request, headers=self.headers("pilot.example.com", "wrong"))[0], 401)

    def test_a_web_page_is_refused_whatever_name_it_uses(self):
        headers = {**self.headers("pilot.example.com"), "Origin": "https://attacker.example"}
        self.assertEqual(self.post(self.request, headers=headers)[0], 403)

    def test_a_listed_name_reaches_the_agents_route_and_nothing_else(self):
        status, _reply = self.post({}, headers=self.headers("pilot.example.com"), path="/admin/reload-extension")
        self.assertEqual(status, 403)
        extension = FakeExtension(self.port, host="pilot.example.com")
        self.addCleanup(extension.close)
        self.assertEqual(extension.status, 403)

    def test_another_name_cannot_be_allowed_without_a_password(self):
        with self.assertRaises(ValueError):
            bridge_module.Bridge(allowed_hosts=["pilot.example.com"])
        with self.assertRaises(SystemExit):
            bridge_module.main(["--allow-host", "pilot.example.com", "--port", "0"])


if __name__ == "__main__":
    unittest.main()
