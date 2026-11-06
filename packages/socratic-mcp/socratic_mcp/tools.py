"""MCP tools that expose a Socratic sidecar.

The contract is the sidecar's HTTP API (docs/SIDECAR-CONTRACT.md); this module
only translates MCP tool calls into requests and wraps the JSON back into
content blocks. No MCP SDK: the stdio protocol is small enough to speak
directly, which keeps the package dependency-free.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

PROTOCOL = "2024-11-05"
VERSION = "0.1.0"

TOOLS = [
    {
        "name": "kb_search",
        "description": "Search the library (private PDFs or public corpora); returns citations "
                       "with a page-image URL or a source URL. Use book+chapter for a scanned "
                       "chapter, document_id+section for a public text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "view": {"type": "string", "enum": ["student", "tutor"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                "source": {"type": "string"},
                "lang": {"type": "string"},
                "book": {"type": "string"},
                "chapter": {"type": "string"},
                "document_id": {"type": "string"},
                "section": {"type": "string"},
                "scope": {"type": "string", "enum": ["auto", "all", "routed"]},
            },
            "required": ["query"],
        },
    },
    {
        "name": "kb_lexical",
        "description": "Exact-substring (grep) or inflection-tolerant (lemma) lookup for "
                       "quotations, names, formulas and identifiers. lemma needs a v2 catalogue.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "mode": {"type": "string", "enum": ["grep", "lemma"]},
                "view": {"type": "string", "enum": ["student", "tutor"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                "source": {"type": "string"},
                "lang": {"type": "string"},
                "book": {"type": "string"},
                "document_id": {"type": "string"},
                "section": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "kb_read",
        "description": "Read one chunk by id (citation included).",
        "inputSchema": {
            "type": "object",
            "properties": {"chunk_id": {"type": "integer"}, "view": {"type": "string"}},
            "required": ["chunk_id"],
        },
    },
    {
        "name": "chapter_lookup",
        "description": "Resolve '卷3' / '第7回' / a title fragment to a page range and page images; "
                       "pass page to find which chapter contains it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "book": {"type": "string"},
                "chapter": {"type": "string"},
                "page": {"type": "integer", "minimum": 1},
                "source": {"type": "string"},
            },
            "required": ["book"],
        },
    },
    {
        "name": "review_session",
        "description": "Freeze a tutoring session and review it: claim verdicts, error classes, practice.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "answers": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "socratic_state",
        "description": "Read the teaching state machine state for a session.",
        "inputSchema": {
            "type": "object",
            "properties": {"session_id": {"type": "string"}},
            "required": ["session_id"],
        },
    },
    {
        "name": "socratic_health",
        "description": "Whether the sidecar is reachable, plus index statistics.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def base_url():
    return os.environ.get("SOCRATIC_SIDECAR_URL", "http://127.0.0.1:8765").rstrip("/")


def _headers():
    token = os.environ.get("SOCRATIC_TOKEN", "")
    return {"Authorization": "Bearer " + token} if token else {}


def _get(path):
    req = urllib.request.Request(base_url() + path, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = {}
        try:
            body = json.loads(e.read() or b"{}")
        except Exception:
            pass
        return {"ok": False, "status": e.code, "body": body}
    except Exception as e:  # connection refused, DNS, timeout
        return {"ok": False, "error": "sidecar_unreachable", "detail": str(e)[:200],
                "base": base_url()}


def _post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base_url() + path, data=data, headers={
        "Content-Type": "application/json", **_headers()})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = {}
        try:
            body = json.loads(e.read() or b"{}")
        except Exception:
            pass
        return {"ok": False, "status": e.code, "body": body}
    except Exception as e:
        return {"ok": False, "error": "sidecar_unreachable", "detail": str(e)[:200],
                "base": base_url()}


def call_tool(name, args):
    """Map one MCP tool call to the sidecar and return a JSON-able result."""
    if name == "kb_search":
        q = {"q": str(args.get("query", "")),
             "view": str(args.get("view", "student")),
             "limit": str(args.get("limit", 8))}
        for key in ("source", "lang", "book", "chapter", "document_id", "section"):
            if args.get(key):
                q[key] = str(args[key])
        if args.get("scope") in ("all", "routed"):
            q["scope"] = str(args["scope"])
        return _get("/v1/search?" + urllib.parse.urlencode(q))
    if name == "kb_lexical":
        mode = "lemma" if str(args.get("mode", "grep")) == "lemma" else "grep"
        q = {"q": str(args.get("query", "")),
             "view": str(args.get("view", "student")),
             "limit": str(args.get("limit", 20))}
        for key in ("source", "lang", "book", "document_id", "section"):
            if args.get(key):
                q[key] = str(args[key])
        return _get("/v1/%s?%s" % (mode, urllib.parse.urlencode(q)))
    if name == "kb_read":
        q = {"view": str(args.get("view", "student"))}
        return _get("/v1/chunks/%d?%s" % (int(args["chunk_id"]), urllib.parse.urlencode(q)))
    if name == "chapter_lookup":
        q = {"book": str(args["book"])}
        if args.get("source"):
            q["source"] = str(args["source"])
        if args.get("chapter"):
            q["q"] = str(args["chapter"])
        if args.get("page"):
            q["page"] = str(args["page"])
        return _get("/v1/chapter?" + urllib.parse.urlencode(q))
    if name == "review_session":
        body = {"session_id": str(args["session_id"])}
        if args.get("answers"):
            body["answers"] = [str(a) for a in args["answers"]]
        return _post("/v1/review", body)
    if name == "socratic_state":
        return _get("/v1/state/" + urllib.parse.quote(str(args["session_id"])))
    if name == "socratic_health":
        return _get("/health")
    raise KeyError(name)
