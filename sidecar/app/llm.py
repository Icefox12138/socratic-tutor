"""One OpenAI-compatible chat client for the runtime.

Two places in the sidecar call a model — the OOV translator (`translate.py`) and
the constrained answer evaluator (`evaluator.py`) — and both go through here.
Endpoint, model and key are configuration, never code:

    SOCRATIC_LLM_BASE      default https://api.deepseek.com
    SOCRATIC_LLM_MODEL     default deepseek-chat
    SOCRATIC_LLM_KEY_FILE  default <repo>/deepseek API key.txt
    DEEPSEEK_API_KEY       takes precedence over the file
    SOCRATIC_LLM_TIMEOUT   default 25 s

Deliberately no retries: both callers degrade instead of blocking a teaching
turn (the translator returns [], the evaluator falls back to a rule verdict),
so a slow or absent endpoint must fail fast.

`chat()` also accepts a `loader(url, payload, headers, timeout) -> dict` seam so
tests can drive it without a network, which is the same seam `translate.py`
already exposed as `opener`.
"""
import json
import os
import time
import urllib.error
import urllib.request

from . import config

DEFAULT_BASE = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT = 25.0


class LlmUnavailable(RuntimeError):
    """No key: the call cannot even be attempted."""


class LlmError(RuntimeError):
    """The endpoint answered, but not with something usable."""


def key():
    """API key from the environment first, then the configured file."""
    from_env = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if from_env:
        return from_env
    for path in (config.LLM_KEY_FILE,
                 os.path.join(os.getcwd(), "deepseek API key.txt")):
        try:
            with open(path, encoding="utf-8") as fh:
                found = fh.read().strip()
        except OSError:
            continue
        if found:
            return found
    return ""


def available():
    return bool(key())


def settings():
    """The resolved route, without the secret."""
    base = str(getattr(config, "LLM_BASE", DEFAULT_BASE) or DEFAULT_BASE)
    model = str(getattr(config, "LLM_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL)
    try:
        timeout = float(os.environ.get("SOCRATIC_LLM_TIMEOUT", DEFAULT_TIMEOUT))
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    return {"base": base.rstrip("/"), "model": model, "timeout": timeout}


def provenance():
    """Copy this into an evaluation result so a number is tied to a route."""
    route = settings()
    return {"base": route["base"], "model": route["model"], "configured": available()}


def _http_json(url, payload, headers, timeout):
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def chat(messages, *, model=None, base=None, temperature=0.0, max_tokens=None,
         timeout=None, loader=None):
    """POST one chat completion; returns content plus the route that served it."""
    route = settings()
    url = (base or route["base"]).rstrip("/") + "/chat/completions"
    payload = {
        "model": model or route["model"],
        "temperature": temperature,
        "messages": messages,
    }
    if max_tokens is not None:
        payload["max_tokens"] = int(max_tokens)
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    secret = key()
    if secret:
        headers["Authorization"] = "Bearer " + secret

    started = time.time()
    fetch = loader or _http_json
    try:
        data = fetch(url, body, headers, timeout or route["timeout"])
    except urllib.error.HTTPError as exc:
        raise LlmError("HTTP %s from %s" % (exc.code, url)) from exc
    except Exception as exc:                       # network, timeout, bad JSON
        raise LlmError("%s: %s" % (type(exc).__name__, exc)) from exc
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmError("unexpected response shape from %s" % url) from exc
    return {
        "content": content,
        "model": payload["model"],
        "base": url.rsplit("/chat/completions", 1)[0],
        "latency_ms": int((time.time() - started) * 1000),
        "usage": data.get("usage") or {},
    }


def parse_json(text):
    """Best-effort object out of a model reply (fences and prose tolerated)."""
    body = str(text or "").strip()
    if not body:
        return None
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(body[start:end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def chat_json(messages, **kwargs):
    """chat() plus a parsed JSON object; returns (data, meta) or (None, meta)."""
    out = chat(messages, **kwargs)
    meta = {k: out[k] for k in ("model", "base", "latency_ms", "usage")}
    return parse_json(out["content"]), meta
