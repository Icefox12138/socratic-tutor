"""Minimal MCP server over stdio (JSON-RPC 2.0, newline-delimited).

  python -m socratic_mcp.server            # uses SOCRATIC_SIDECAR_URL / SOCRATIC_TOKEN

Speaks just enough of the protocol for an agent host: initialize, tools/list,
tools/call, ping. No third-party dependencies.
"""
import json
import sys

from . import tools


def _ok(mid, result):
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _err(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle(msg):
    """One request -> one response (or None for notifications)."""
    method = msg.get("method")
    mid = msg.get("id")
    if mid is None:                                  # notification
        return None
    if method == "initialize":
        return _ok(mid, {
            "protocolVersion": tools.PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "socratic-sidecar", "version": tools.VERSION},
        })
    if method == "ping":
        return _ok(mid, {})
    if method == "tools/list":
        return _ok(mid, {"tools": tools.TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        if not any(t["name"] == name for t in tools.TOOLS):
            return _err(mid, -32602, "unknown tool: %s" % name)
        try:
            result = tools.call_tool(name, args)
        except KeyError as e:
            return _err(mid, -32602, "bad arguments for %s: %s" % (name, e))
        except Exception as e:  # never crash the transport on one bad call
            return _err(mid, -32603, str(e)[:200])
        failed = isinstance(result, dict) and result.get("ok") is False
        return _ok(mid, {"content": [{"type": "text",
                                      "text": json.dumps(result, ensure_ascii=False)}],
                         "isError": bool(failed)})
    return _err(mid, -32601, "method not found: %s" % method)


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            sys.stdout.write(json.dumps(_err(None, -32700, "parse error")) + "\n")
            sys.stdout.flush()
            continue
        out = handle(msg)
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
