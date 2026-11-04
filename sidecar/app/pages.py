"""On-demand page rendering with a local LRU cache.

Rendering uses pypdfium2 (Apache-2.0 / BSD-3-Clause), not PyMuPDF, so the whole
repository can stay MIT.
"""
import hashlib
import os

import pypdfium2 as pdfium

from . import config

CACHE_CAP = 2 * 1024 ** 3
ROOTS = {
    "library": os.path.join(config.LIBRARY, "PDF"),
    "steadman": os.path.join(config.LIBRARY, "PDF-new", "Steadman"),
    "teubner_conte": os.path.join(config.LIBRARY, "teubner"),
}


def _inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) == os.path.abspath(root)
    except ValueError:
        return False


def resolve(source: str, book: str) -> str:
    if source == "steadman":
        for lang in ("greek", "latin"):
            p = os.path.join(ROOTS["steadman"], lang, book + ".pdf")
            if os.path.exists(p) and _inside(p, ROOTS["steadman"]):
                return p
    elif source == "library":
        p = os.path.join(ROOTS["library"], book)
        if os.path.exists(p) and _inside(p, ROOTS["library"]):
            return p
    elif source == "teubner_conte":
        p = os.path.join(ROOTS["teubner_conte"], "conte_aeneis.pdf")
        if os.path.exists(p) and _inside(p, ROOTS["teubner_conte"]):
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


def count(source: str, book: str) -> int:
    """Page count for one book (cached; used by the page browser)."""
    key = (source, book)
    if key in _COUNTS:
        return _COUNTS[key]
    if source not in ROOTS:
        raise ValueError("unknown source")
    path = resolve(source, book)
    doc = pdfium.PdfDocument(path)
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
    path = resolve(source, book)
    key = f"{source}__{hashlib.sha1(book.encode('utf-8')).hexdigest()[:10]}__p{page}_{dpi}"
    if bbox:
        key += "_" + "_".join(f"{x:.3f}" for x in bbox)
    out = os.path.join(config.CACHE, key + ".png")
    if os.path.exists(out):
        with open(out, "rb") as fh:
            return fh.read()

    os.makedirs(config.CACHE, exist_ok=True)
    doc = pdfium.PdfDocument(path)
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
        bitmap.to_pil().save(out, format="PNG", optimize=False)
    finally:
        doc.close()
    _evict()
    with open(out, "rb") as fh:
        return fh.read()
