"""On-demand page rendering with a local LRU cache."""
import hashlib
import os

import pymupdf

from . import config

CACHE_CAP = 2 * 1024 ** 3
ROOTS = {
    "library": os.path.join(config.ROOT, "PDF"),
    "steadman": os.path.join(config.ROOT, "PDF-new", "Steadman"),
    "teubner_conte": os.path.join(config.ROOT, "teubner"),
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
    doc = pymupdf.open(path)
    try:
        _COUNTS[key] = doc.page_count
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
        return open(out, "rb").read()

    os.makedirs(config.CACHE, exist_ok=True)
    doc = pymupdf.open(path)
    try:
        if not (1 <= page <= doc.page_count):
            raise ValueError(f"page out of 1..{doc.page_count}")
        pg = doc.load_page(page - 1)
        if bbox:
            x0, y0, x1, y1 = bbox
            if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
                raise ValueError("bbox must be normalized [x0,y0,x1,y1]")
            rect = pg.rect
            clip = pymupdf.Rect(rect.x0 + x0 * rect.width, rect.y0 + y0 * rect.height,
                                rect.x0 + x1 * rect.width, rect.y0 + y1 * rect.height)
            pix = pg.get_pixmap(dpi=dpi, clip=clip)
        else:
            pix = pg.get_pixmap(dpi=dpi)
        pix.save(out)
    finally:
        doc.close()
    _evict()
    return open(out, "rb").read()
