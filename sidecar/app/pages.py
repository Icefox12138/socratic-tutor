"""On-demand page rendering with a local LRU cache.

Rendering uses pypdfium2 (Apache-2.0 / BSD-3-Clause), not PyMuPDF, so the whole
repository can stay MIT.
"""
import hashlib
import os
import threading

from . import citation_policy, config


class RendererUnavailable(RuntimeError):
    """Page rendering is switched off, or pypdfium2 is not installed."""


def _pdfium():
    try:
        import pypdfium2
    except ImportError as e:      # pragma: no cover - depends on the install
        raise RendererUnavailable("pypdfium2 is not installed: %s" % e)
    return pypdfium2


# PDFium is not thread-safe: two documents open at once in one process corrupt its
# internal state, which surfaces as "Failed to load page" / "Data format error" and
# can crash the process natively. FastAPI runs these sync endpoints in a thread
# pool, so every PDFium call — open, page access, render, close — is serialized.
# A render is ~0.2 s, which is fine for a single reader.
_PDFIUM_LOCK = threading.Lock()

CACHE_CAP = 2 * 1024 ** 3

#: the layout an unconfigured install has always had
_LEGACY_ROOTS = {
    "library": os.path.join(config.LIBRARY, "PDF"),
    "steadman": os.path.join(config.LIBRARY, "PDF-new", "Steadman"),
    "teubner_conte": os.path.join(config.LIBRARY, "teubner"),
}

#: pages source name -> directory. Still a plain mutable dict because the
#: serving path and the tests mutate it; the *values* come from the policy's
#: local-file channels (see refresh_roots), with the legacy layout as fallback.
ROOTS = dict(_LEGACY_ROOTS)


def refresh_roots():
    """Re-derive ROOTS from the policy, then from SOCRATIC_PAGE_ROOTS.

    A policy channel wins over the legacy default; a source the policy does not
    describe keeps the legacy path, so an unconfigured install is unchanged.
    ``SOCRATIC_PAGE_ROOTS="name=<dir>[;name2=<dir2>]"`` adds (or overrides)
    sources for corpora the engine does not know — /v1/pages then serves them
    flat (<dir>/<book>).
    """
    from_policy = citation_policy.local_roots()
    roots = {}
    for name, path in _LEGACY_ROOTS.items():
        roots[name] = from_policy.get(name) or path
    for pair in (config.PAGE_ROOTS or "").split(";"):
        name, sep, path = pair.strip().partition("=")
        name, path = name.strip(), path.strip()
        if sep and name and path:
            roots[name] = os.path.abspath(os.path.expanduser(path))
    ROOTS.clear()
    ROOTS.update(roots)
    return ROOTS


refresh_roots()


def _inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) == os.path.abspath(root)
    except ValueError:
        return False


def resolve(source: str, book: str) -> str:
    """Locate one book's PDF: legacy layouts for the built-in sources, flat
    ``<root>/<book>[.pdf]`` for anything else (policy or SOCRATIC_PAGE_ROOTS)."""
    root = ROOTS.get(source)
    if not root:
        raise FileNotFoundError(f"{source}/{book}")
    candidates = []
    if source == "steadman":
        candidates += [os.path.join(root, lang, book + ".pdf")
                       for lang in ("greek", "latin")]
    elif source == "teubner_conte":
        candidates.append(os.path.join(root, "conte_aeneis.pdf"))
    candidates += [os.path.join(root, book), os.path.join(root, book + ".pdf")]
    for p in candidates:
        if os.path.exists(p) and _inside(p, root):
            return p
    raise FileNotFoundError(f"{source}/{book}")


def _evict():
    files, total = [], 0
    for dp, _d, fs in os.walk(config.CACHE):
        for f in fs:
            p = os.path.join(dp, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            files.append((st.st_mtime, st.st_size, p))
            total += st.st_size
    if total <= CACHE_CAP:
        return
    files.sort()
    for _m, size, p in files:
        if total <= CACHE_CAP:
            break
        try:
            os.remove(p)
            total -= size
        except OSError:
            pass


_COUNTS = {}


def _require_render(source):
    """A source may only render if one of its channels provides page_render.

    The policy names capabilities per channel; a source backed by a search-only
    channel (a RAG database without the original files) fails here with a typed
    error instead of a 500 from PDFium.
    """
    sid = citation_policy.PAGES_SOURCE.get(source)
    if sid:
        citation_policy.require(sid, "page_render")


def count(source: str, book: str) -> int:
    """Page count for one book (cached; used by the page browser)."""
    key = (source, book)
    if key in _COUNTS:
        return _COUNTS[key]
    if source not in ROOTS:
        raise ValueError("unknown source")
    _require_render(source)
    path = resolve(source, book)
    with _PDFIUM_LOCK:
        doc = _pdfium().PdfDocument(path)
        try:
            _COUNTS[key] = len(doc)
        finally:
            doc.close()
    return _COUNTS[key]


def render(source: str, book: str, page: int, dpi: int = 150, bbox=None) -> bytes:
    if source not in ROOTS:
        raise ValueError("unknown source")
    if not (72 <= dpi <= 300):
        raise ValueError("dpi must be 72..300")
    _require_render(source)
    path = resolve(source, book)
    key = f"{source}__{hashlib.sha1(book.encode('utf-8')).hexdigest()[:10]}__p{page}_{dpi}"
    if bbox:
        key += "_" + "_".join(f"{x:.3f}" for x in bbox)
    out = os.path.join(config.CACHE, key + ".png")
    if os.path.exists(out):
        with open(out, "rb") as fh:
            return fh.read()

    os.makedirs(config.CACHE, exist_ok=True)
    with _PDFIUM_LOCK:
        doc = _pdfium().PdfDocument(path)
        try:
            total = len(doc)
            if not (1 <= page <= total):
                raise ValueError(f"page out of 1..{total}")
            pg = doc[page - 1]
            crop = None
            if bbox:
                x0, y0, x1, y1 = bbox
                if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
                    raise ValueError("bbox must be normalized [x0,y0,x1,y1]")
                # pypdfium2's crop is an inset margin tuple (left, bottom, right, top)
                # in points, measured from each edge — not an absolute rectangle.
                w, h = pg.get_size()
                crop = (x0 * w, (1 - y1) * h, (1 - x1) * w, y0 * h)
            # pypdfium2 rejects crop=None, so only pass it when a box was given
            bitmap = pg.render(scale=dpi / 72, **({"crop": crop} if crop else {}))
            # Write a sibling temp file and publish it atomically: a concurrent
            # request that passes the exists() check above while the PNG is
            # still being written must never read a half-written file.
            tmp = out + ".%d.tmp" % os.getpid()
            bitmap.to_pil().save(tmp, format="PNG", optimize=False)
            os.replace(tmp, out)
        finally:
            doc.close()
    _evict()
    with open(out, "rb") as fh:
        return fh.read()
