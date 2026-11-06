"""Minimal HTTP GET with a descriptive User-Agent.

Wikimedia requires a UA that identifies the tool and a contact; Python's
default ``Python-urllib/3.x`` is answered with 403. Callers may inject their own
opener (tests do) so no test ever needs the network.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request


class HttpError(RuntimeError):
    def __init__(self, status, url, body=""):
        super().__init__("HTTP %s for %s" % (status, url))
        self.status = status
        self.url = url
        self.body = body[:400]


def default_user_agent():
    import os
    return os.environ.get(
        "SOCRATIC_HTTP_UA",
        "socratic-tutor/0.1 (local Socratic tutor; contact: administrator@localhost)",
    )


def get(url, params=None, user_agent=None, timeout=30, headers=None):
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    hdrs = {"User-Agent": user_agent or default_user_agent(),
            "Accept": "application/json, text/xml;q=0.9, */*;q=0.8"}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, url, e.read().decode("utf-8", "replace"))
    except urllib.error.URLError as e:
        raise HttpError(0, url, str(e.reason))


class RateLimiter:
    """One request per ``min_interval`` seconds; no sleeping when interval is 0."""

    def __init__(self, min_interval=1.0, clock=time.monotonic, sleep=time.sleep):
        self.min_interval = max(0.0, float(min_interval or 0))
        self._clock = clock
        self._sleep = sleep
        self._last = None

    def wait(self):
        if not self.min_interval:
            return
        now = self._clock()
        if self._last is not None:
            delta = now - self._last
            if delta < self.min_interval:
                self._sleep(self.min_interval - delta)
        self._last = self._clock()


def get_json(url, params=None, **kwargs):
    body, _ctype = get(url, params=params, **kwargs)
    try:
        return json.loads(body.decode("utf-8"))
    except ValueError as e:
        raise HttpError(0, url, "not JSON: %s" % e)
