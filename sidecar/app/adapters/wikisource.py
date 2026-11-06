"""Wikisource (MediaWiki) adapter.

Wikisource is citation-grade because every page has a permanent revision id:
``oldid`` pins exactly the text a quotation was checked against. The adapter
parses the *rendered* HTML (``action=parse``) rather than wikitext, so templates,
footnotes and edit links never leak into a quotation.

Only ``/w/api.php`` is used. No scraping, no ``action=raw`` on arbitrary hosts,
and the User-Agent identifies the tool as Wikimedia policy requires.
"""
import re
from html.parser import HTMLParser
from urllib.parse import quote

from .. import textutil
from .base import Document, FetchError, Section, SourceSpec
from .http import RateLimiter, get_json, default_user_agent

API_PATH = "/w/api.php"

# Wikisource language codes -> the project's language names.
LANG_MAP = {"zh": "zh-classical", "la": "latin", "el": "greek",
            "grc": "greek", "en": "en"}

# Elements whose text is navigation, not source text.
_SKIP_TAGS = {"script", "style", "noscript", "sup", "audio", "video", "img", "map"}
_SKIP_CLASSES = {
    "mw-editsection", "reference", "references", "noprint", "navbox",
    "sistersitebox", "metadata", "mbox", "ombox", "hatnote", "rellink", "ambox",
    "toc", "mw-cite-backlink", "printfooter", "catlinks", "mw-jump-link",
    "navigation-not-searchable",
    # Wikisource {{header}} and its navigation/licence boxes
    "ws-header", "header_notes", "ws-summary", "licensecontainer",
    "mw-references-wrap", "reflist", "ws-noexport", "ws-nav",
}
_HEADINGS = {"h1", "h2", "h3", "h4"}
_BLOCKS = {"p", "div", "li", "tr", "td", "th", "dd", "dt", "blockquote",
           "pre", "table", "ul", "ol", "section"}
_BR = "br"


class _SectionParser(HTMLParser):
    """Rendered HTML -> ``[(heading, text), …]``."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections = []
        self._buf = []
        self._heading = []
        self._heading_tag = None
        self._title = ""
        self._skip_tag = None
        self._skip_depth = 0

    # -- element handling -------------------------------------------------
    def _skippable(self, tag, attrs):
        classes = set((attrs.get("class") or "").split())
        return tag in _SKIP_TAGS or bool(classes & _SKIP_CLASSES)

    def handle_starttag(self, tag, attrs):
        if self._skip_tag:
            self._skip_depth += 1
            return
        if self._skippable(tag, dict(attrs)):
            self._skip_tag = tag
            self._skip_depth = 1
            return
        if tag in _HEADINGS:
            self._flush()
            self._heading_tag = tag
            self._heading = []
            return
        if tag == _BR:
            self._append("\n")
        elif tag in _BLOCKS:
            self._append("\n\n")

    def handle_startendtag(self, tag, attrs):
        # HTMLParser calls starttag+endtag by default; keep the break once.
        if tag == _BR:
            self._append("\n")
            return
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self._skip_tag:
            self._skip_depth -= 1
            if self._skip_depth <= 0:
                self._skip_tag = None
                self._skip_depth = 0
            return
        if self._heading_tag and tag == self._heading_tag:
            self._title = textutil.clean_text("".join(self._heading))
            self._heading_tag = None
            self._heading = []
            self._buf = []
            return
        if tag in _BLOCKS:
            self._append("\n\n")

    def handle_data(self, data):
        if self._skip_tag:
            return
        if self._heading_tag:
            self._heading.append(data)
        else:
            self._append(data)

    # -- accumulation -----------------------------------------------------
    def _append(self, s):
        if self._heading_tag:
            self._heading.append(s)
        else:
            self._buf.append(s)

    def _flush(self):
        text = textutil.clean_text("".join(self._buf))
        if text:
            self.sections.append((self._title, text))
        self._buf = []

    def close(self):
        super().close()
        self._flush()


def extract_sections(html: str):
    """Public helper: HTML -> ``[(heading, plain_text)]``."""
    if not html:
        return []
    parser = _SectionParser()
    try:
        parser.feed(html)
    except Exception as e:                        # malformed markup is not fatal
        raise FetchError("could not parse rendered HTML: %s" % e)
    parser.close()
    return parser.sections


class MediaWikiClient:
    def __init__(self, api_url, user_agent=None, timeout=30, min_interval=1.0,
                 opener=None):
        self.api_url = api_url
        self.user_agent = user_agent or default_user_agent()
        self.timeout = timeout
        self._limiter = RateLimiter(min_interval)
        self._opener = opener or get_json

    def call(self, params):
        self._limiter.wait()
        payload = dict(params)
        payload.setdefault("format", "json")
        payload.setdefault("formatversion", "2")
        try:
            data = self._opener(self.api_url, params=payload,
                                user_agent=self.user_agent, timeout=self.timeout)
        except Exception as e:
            raise FetchError(str(e))
        if not isinstance(data, dict):
            raise FetchError("API returned %r" % type(data).__name__)
        err = data.get("error")
        if err:
            raise FetchError("%s: %s" % (err.get("code"), err.get("info")))
        return data


class WikisourceAdapter:
    def __init__(self, lang="zh", api_url=None, license="CC-BY-SA-4.0",
                 redistribution="share-alike", user_agent=None, timeout=30,
                 min_interval=1.0, opener=None):
        self.lang = lang
        self.site = "%s.wikisource.org" % lang
        self.api_url = api_url or "https://%s%s" % (self.site, API_PATH)
        self.license = license
        self.redistribution = redistribution
        self.client = MediaWikiClient(self.api_url, user_agent=user_agent,
                                      timeout=timeout, min_interval=min_interval,
                                      opener=opener)

    @property
    def source_id(self):
        return "wikisource:%s" % self.lang

    def source(self) -> SourceSpec:
        return SourceSpec(
            source_id=self.source_id,
            adapter="mediawiki",
            base_url=self.api_url,
            license=self.license,
            redistribution=self.redistribution,
            rate_limit=self.client._limiter.min_interval,
            config={"lang": self.lang, "site": self.site,
                    "api": self.api_url},
        )

    def fetch(self, title, author=None, edition=None):
        data = self.client.call({
            "action": "parse",
            "page": title,
            "prop": "text|revid|displaytitle",
            "redirects": "1",
        })
        parsed = data.get("parse")
        if not parsed:
            raise FetchError("no parse result for %r" % title)
        resolved = parsed.get("title") or title
        revision = str(parsed.get("revid") or "")
        sections = extract_sections(parsed.get("text") or "")
        if not sections:
            raise FetchError("page %r has no quotable text" % title)

        out = []
        for i, (heading, text) in enumerate(sections):
            locator = {"scheme": "mediawiki", "site": self.site,
                       "title": resolved, "revision": revision,
                       "section_index": i}
            if heading:
                locator["section"] = heading
            out.append(Section(title=heading or "（正文）", text=text,
                               locator=locator, ordinal=i,
                               quality="rendered-html"))
        document_id = "%s:%s" % (self.source_id, resolved)
        href = "https://%s/wiki/%s" % (self.site, quote(resolved.replace(" ", "_")))
        if revision:
            href += "?oldid=%s" % quote(revision)
        return Document(
            document_id=document_id,
            source_id=self.source_id,
            title=resolved,
            sections=out,
            lang=LANG_MAP.get(self.lang, self.lang),
            author=author,
            edition=edition or "Wikisource",
            script="Hans" if self.lang == "zh" else None,
            license=self.license,
            provenance="%s %s rev %s" % (self.site, resolved, revision),
            canonical_url=href,
            metadata={"site": self.site, "pageid": parsed.get("pageid"),
                      "revision": revision, "api": self.api_url},
            source_version=revision,
        )

    def search(self, query, limit=10):
        data = self.client.call({"action": "query", "list": "search",
                                 "srsearch": query, "srlimit": max(1, min(int(limit), 50))})
        return [r.get("title") for r in (data.get("query", {}).get("search") or [])]

    def categories(self, title):
        data = self.client.call({"action": "query", "prop": "categories",
                                 "titles": title, "cllimit": "max"})
        pages = (data.get("query", {}) or {}).get("pages") or []
        if isinstance(pages, dict):
            pages = list(pages.values())
        out = []
        for page in pages:
            for c in page.get("categories") or []:
                name = c.get("title") or ""
                out.append(re.sub(r"^[^:]+:", "", name))
        return out
