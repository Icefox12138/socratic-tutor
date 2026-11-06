"""Perseus / CTS adapter.

A CTS citation is a URN — a work, a book and a line — not a page. Two endpoints
exist: Perseus's legacy ``/hopper/CTS`` (reachable and still serving TEI) and
the newer ``scaife-cts`` host, which some networks cannot reach (TLS SNI is
rejected). The legacy endpoint does not support passage ranges, so callers pass
one URN per passage and :meth:`fetch_many` merges them into one document.

The locator stores the full URN plus the parsed line window. The document id is
the edition-level work URN, so every passage of one edition lands in one
document.
"""
import re
import xml.etree.ElementTree as ET

from .. import textutil
from .base import Document, FetchError, Section, SourceSpec
from .http import RateLimiter, get, default_user_agent

TEI = "{http://www.tei-c.org/ns/1.0}"
CTS = "{http://chs.harvard.edu/xmlns/cts3}"
PASSAGE_RE = re.compile(r":(\d+)\.(\d+)(?:-(\d+)\.(\d+))?$")
LEGACY_API = "https://www.perseus.tufts.edu/hopper/CTS"

LANG_MAP = {"grc": "greek", "greek": "greek", "lat": "latin", "la": "latin",
            "eng": "en", "en": "en"}


class CtsAdapter:
    def __init__(self, base_url=LEGACY_API, lang="greek", license="CC-BY-SA-4.0",
                 redistribution="share-alike", user_agent=None, timeout=40,
                 min_interval=1.0, opener=None):
        self.base_url = base_url
        self.lang = lang
        self.license = license
        self.redistribution = redistribution
        self.user_agent = user_agent or default_user_agent()
        self.timeout = timeout
        self._limiter = RateLimiter(min_interval)
        self._opener = opener or get

    @property
    def source_id(self):
        return "perseus"

    def source(self) -> SourceSpec:
        return SourceSpec(
            source_id=self.source_id,
            adapter="cts",
            base_url=self.base_url,
            license=self.license,
            redistribution=self.redistribution,
            rate_limit=self._limiter.min_interval,
            config={"lang": self.lang},
        )

    def _get_passage(self, urn):
        self._limiter.wait()
        try:
            body, _ctype = self._opener(
                self.base_url, params={"request": "GetPassage", "urn": urn},
                user_agent=self.user_agent, timeout=self.timeout)
        except Exception as e:
            raise FetchError(str(e))
        if isinstance(body, str):
            body = body.encode("utf-8")
        return body

    def fetch(self, urn, title=None, author=None, edition=None, lang=None,
              license=None):
        urn = urn.strip()
        if not urn.startswith("urn:cts:"):
            raise FetchError("not a CTS URN: %r" % urn)
        body = self._get_passage(urn)
        try:
            root = ET.fromstring(body)
        except ET.ParseError as e:
            raise FetchError("CTS returned non-XML: %s" % e)
        reply = root.find(".//" + CTS + "reply")
        error = (reply is not None and reply.get("name") == "CTSError") or \
            root.find(".//" + CTS + "CTSError") is not None
        if error:
            raise FetchError("CTS error for %s" % urn)

        work = _text(root.find(".//" + CTS + "workUrn")) or work_urn(urn)
        book, line_start, line_end = passage(urn)
        meta_title = title or _text(root.find(".//" + CTS + "title")) \
            or work.rsplit(":", 1)[-1]
        meta_author = author or _text(root.find(".//" + CTS + "groupname"))
        version = _text(root.find(".//" + CTS + "versionInfo"))
        tei_text = root.find(".//" + TEI + "text")
        xml_lang = tei_text.get("{http://www.w3.org/XML/1998/namespace}lang") \
            if tei_text is not None else None

        divs = root.findall(".//" + TEI + "div")
        lines = []
        if divs:
            for div in divs:
                t = textutil.clean_text("".join(div.itertext()))
                if t:
                    lines.append(t)
        elif tei_text is not None:
            t = textutil.clean_text("".join(tei_text.itertext()))
            if t:
                lines.append(t)
        if not lines:
            raise FetchError("CTS passage %s has no text" % urn)

        sections = []
        for i, text in enumerate(lines):
            locator = {"scheme": "cts", "urn": urn, "work": work,
                       "book": book, "line_start": line_start,
                       "line_end": line_end if line_end is not None else line_start}
            sections.append(Section(title=_label(book, line_start, line_end),
                                    text=text, locator=locator, ordinal=i,
                                    quality="tei-passage"))
        return Document(
            document_id=work,
            source_id=self.source_id,
            title=meta_title,
            sections=sections,
            lang=LANG_MAP.get((lang or xml_lang or self.lang).lower(), self.lang),
            author=meta_author,
            edition=edition or version or "Perseus Digital Library",
            script=None,
            license=license or self.license,
            provenance="%s %s" % (self.base_url, urn),
            canonical_url="https://scaife.perseus.org/reader/%s" % work,
            metadata={"urn": urn, "work": work, "book": book,
                      "base": self.base_url, "version": version},
            source_version=work,
        )

    def fetch_many(self, urns, title=None, author=None, skip_errors=False,
                   **kwargs):
        """Fetch several passages of one work into one document.

        The legacy endpoint refuses some line numbers (and some editions), so
        ``skip_errors`` lets a book-level import continue while recording what
        was skipped instead of aborting the whole document.
        """
        if not urns:
            raise FetchError("no URNs given")
        docs, skipped = [], []
        for urn in urns:
            try:
                docs.append(self.fetch(urn, title=title, author=author, **kwargs))
            except FetchError as e:
                if not skip_errors:
                    raise
                skipped.append({"urn": urn, "error": str(e)[:120]})
        if not docs:
            raise FetchError("no passages fetched")
        first = docs[0]
        sections = []
        for doc in docs:
            for sec in doc.sections:
                sec.ordinal = len(sections)
                sections.append(sec)
        first.sections = sections
        first.metadata["skipped"] = skipped
        return first


def _text(el):
    return textutil.clean_text("".join(el.itertext())) if el is not None else ""


def _label(book, start, end):
    if book is None or start is None:
        return "passage"
    if end is None or end == start:
        return "%s.%s" % (book, start)
    return "%s.%s-%s.%s" % (book, start, book, end)


def work_urn(urn: str) -> str:
    """Drop a trailing passage (``:1.1-1.10``) from a CTS URN."""
    return PASSAGE_RE.sub("", urn)


def passage(urn: str):
    """Return ``(book, line_start, line_end)`` from a CTS URN, or Nones."""
    m = PASSAGE_RE.search(urn)
    if not m:
        return None, None, None
    book = m.group(1)
    start = int(m.group(2))
    end = int(m.group(4) or m.group(2))
    return book, start, end
