import json
import subprocess
import sys
import unittest

from socratic_mcp import server, tools


class TestProtocol(unittest.TestCase):
    def test_initialize(self):
        out = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(out["result"]["protocolVersion"], tools.PROTOCOL)
        self.assertIn("tools", out["result"]["capabilities"])

    def test_tools_list(self):
        out = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = [t["name"] for t in out["result"]["tools"]]
        for want in ("kb_search", "kb_read", "chapter_lookup", "review_session", "socratic_health"):
            self.assertIn(want, names)

    def test_unknown_tool(self):
        out = server.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                             "params": {"name": "nope", "arguments": {}}})
        self.assertEqual(out["error"]["code"], -32602)

    def test_notification_has_no_response(self):
        self.assertIsNone(server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_unreachable_sidecar_is_a_tool_error_not_a_crash(self):
        old = tools.os.environ.get("SOCRATIC_SIDECAR_URL")
        tools.os.environ["SOCRATIC_SIDECAR_URL"] = "http://127.0.0.1:9"
        try:
            out = server.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                                 "params": {"name": "socratic_health", "arguments": {}}})
            self.assertTrue(out["result"]["isError"])
            body = json.loads(out["result"]["content"][0]["text"])
            self.assertEqual(body["error"], "sidecar_unreachable")
        finally:
            if old is None:
                tools.os.environ.pop("SOCRATIC_SIDECAR_URL", None)
            else:
                tools.os.environ["SOCRATIC_SIDECAR_URL"] = old


class TestStdio(unittest.TestCase):
    def test_roundtrip_over_stdio(self):
        proc = subprocess.Popen([sys.executable, "-m", "socratic_mcp.server"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True)
        try:
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
            self.assertIn("protocolVersion", json.loads(line)["result"])
        finally:
            proc.kill()
            for stream in (proc.stdin, proc.stdout):
                try:
                    stream.close()
                except Exception:
                    pass
            proc.wait(timeout=5)
