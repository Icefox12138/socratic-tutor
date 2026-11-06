"""Typed citation locators for schema v2.

A locator is the unit a citation can be checked against. v1 could say "page 12"
and stop; v2 has to say which scheme, which revision, which line. Keeping the
union in one module means search, verify and the adapters agree on the keys.
"""
import json
from urllib.parse import quote

SCHEMES = ("pdf_page", "mediawiki", "cts", "lean", "dataset", "ia")

REQUIRED = {
    "pdf_page": ("page",),
    "mediawiki": ("site", "title", "revision"),
    "cts": ("urn",),
    "lean": ("module", "decl"),
    "dataset": ("dataset", "id"),
    "ia": ("item", "page"),
}


class LocatorError(ValueError):
    pass


def dumps(locator) -> str:
    return json.dumps(locator, ensure_ascii=False, sort_keys=True)


def loads(raw):
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        val = json.loads(raw)
    except (TypeError, ValueError):
        return {"scheme": "raw", "value": str(raw)}
    return val if isinstance(val, dict) else {"scheme": "raw", "value": str(raw)}


def scheme(locator) -> str:
    return str(loads(locator).get("scheme") or "unknown")


def validate(locator):
    loc = loads(locator)
    sch = loc.get("scheme")
    if sch not in SCHEMES:
        raise LocatorError("unknown locator scheme: %r" % sch)
    missing = [k for k in REQUIRED[sch] if loc.get(k) in (None, "")]
    if missing:
        raise LocatorError("%s locator is missing %s" % (sch, ", ".join(missing)))
    return loc


def url(locator, doc=None):
    """A human-openable URL for the citation, or None when there is no web copy."""
    loc = loads(locator)
    sch = loc.get("scheme")
    if sch == "mediawiki":
        site = loc.get("site") or "wikisource.org"
        title = str(loc.get("title") or "")
        href = "https://%s/wiki/%s" % (site, quote(title.replace(" ", "_")))
        if loc.get("revision"):
            href += "?oldid=%s" % quote(str(loc["revision"]))
        if loc.get("section"):
            href += "#%s" % quote(str(loc["section"]).replace(" ", "_"))
        return href
    if sch == "cts":
        return "https://scaife.perseus.org/reader/%s" % quote(str(loc.get("urn")), safe=":.-_")
    if sch == "dataset":
        return loc.get("url")
    if sch == "lean":
        base = loc.get("repo_url") or "https://github.com/leanprover-community/mathlib4"
        return "%s/blob/%s/%s" % (base, loc.get("mathlib_rev") or "master",
                                  quote(str(loc.get("module") or "").replace(".", "/")))
    if sch == "ia":
        page = loc.get("page")
        return "https://archive.org/details/%s/page/%s" % (quote(str(loc.get("item"))), page)
    if doc:
        return (doc.get("canonical_url") if isinstance(doc, dict) else None)
    return None


def default_label(locator, doc=None) -> str:
    """A readable label when the adapter did not store one."""
    loc = loads(locator)
    sch = loc.get("scheme")
    title = (doc or {}).get("title") if isinstance(doc, dict) else None
    lang = str((doc or {}).get("lang") or "") if isinstance(doc, dict) else ""
    if sch == "mediawiki":
        title = title or loc.get("title") or ""
        section = str(loc.get("section") or "")
        if lang.startswith("zh"):
            label = "《%s》%s" % (title, section) if section else "《%s》" % title
            if loc.get("revision"):
                label += "（Wikisource rev %s）" % loc["revision"]
            return label
        label = str(title)
        if section:
            label += " · " + section
        if loc.get("revision"):
            label += " (Wikisource rev %s)" % loc["revision"]
        return label
    if sch == "cts":
        book = loc.get("book")
        start = loc.get("line_start")
        end = loc.get("line_end")
        span = ""
        if book is not None and start is not None:
            span = "%s.%s" % (book, start)
            if end is not None and end != start:
                span += "-%s.%s" % (book, end)
        elif loc.get("urn"):
            span = str(loc["urn"]).rsplit(":", 1)[-1]
        return ("%s %s" % (title or "CTS", span)).strip()
    if sch == "pdf_page":
        return "%s p.%s" % (title or loc.get("book") or "?", loc.get("page"))
    if sch == "dataset":
        return "%s · %s" % (loc.get("dataset"), loc.get("id"))
    if sch == "lean":
        return "%s.%s" % (loc.get("module"), loc.get("decl"))
    if sch == "ia":
        return "%s p.%s" % (loc.get("item"), loc.get("page"))
    return str(loc)


def revision(locator):
    loc = loads(locator)
    return loc.get("revision") or loc.get("source_version")
