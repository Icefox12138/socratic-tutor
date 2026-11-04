import hashlib
import json
import os
import time

import pymupdf

BASE = r"D:\Guo-Code"
CACHE = os.path.join(BASE, "socratic-tutor", "eval", "p1", "pages")
os.makedirs(CACHE, exist_ok=True)
CAP = 2 * 1024 ** 3

MANIFEST = json.load(open(os.path.join(BASE, "socratic-tutor", "eval", "p0", "catalog", "sample-manifest.json"), encoding="utf-8"))
BY_ID = {s["id"]: s for s in MANIFEST["samples"]}


def resolve(source, book):
    if source == "steadman":
        for lang in ("greek", "latin"):
            p = os.path.join(BASE, "PDF-new", "Steadman", lang, book + ".pdf")
            if os.path.exists(p):
                return p
    if source == "library":
        p = os.path.join(BASE, "PDF", book)
        if os.path.exists(p):
            return p
    if source == "teubner_conte":
        return os.path.join(BASE, "teubner", "conte_aeneis.pdf")
    raise FileNotFoundError(f"{source}/{book}")


def _evict():
    files = []
    total = 0
    for dp, _d, fs in os.walk(CACHE):
        for f in fs:
            p = os.path.join(dp, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            files.append((st.st_mtime, st.st_size, p))
            total += st.st_size
    if total <= CAP:
        return 0
    files.sort()
    removed = 0
    for _m, size, p in files:
        if total <= CAP:
            break
        try:
            os.remove(p)
            total -= size
            removed += 1
        except OSError:
            pass
    return removed


def render(source, book, page, dpi=150, bbox=None):
    t0 = time.perf_counter()
    key = f"{source}__{hashlib.sha1(book.encode('utf-8')).hexdigest()[:10]}__p{page}_{dpi}"
    if bbox:
        key += "_" + "_".join(f"{x:.3f}" for x in bbox)
    out = os.path.join(CACHE, key + ".png")
    if os.path.exists(out):
        return {"path": out, "bytes": os.path.getsize(out), "cached": True,
                "ms": round((time.perf_counter() - t0) * 1000, 1)}
    path = resolve(source, book)
    doc = pymupdf.open(path)
    if not (1 <= page <= doc.page_count):
        doc.close()
        raise ValueError(f"page {page} out of 1..{doc.page_count}")
    pg = doc.load_page(page - 1)
    if bbox:
        rect = pg.rect
        clip = pymupdf.Rect(rect.x0 + bbox[0] * rect.width, rect.y0 + bbox[1] * rect.height,
                            rect.x0 + bbox[2] * rect.width, rect.y0 + bbox[3] * rect.height)
        pix = pg.get_pixmap(dpi=dpi, clip=clip)
    else:
        pix = pg.get_pixmap(dpi=dpi)
    doc.close()

    pix.save(out)
    return {"path": out, "bytes": os.path.getsize(out), "cached": False,
            "ms": round((time.perf_counter() - t0) * 1000, 1)}


if __name__ == "__main__":
    tests = [
        ("steadman", "platos-apology__apology.04jan25", 84, None),
        ("library", os.path.relpath(BY_ID["C1"]["path"], os.path.join(BASE, "PDF")), 76, None),
        ("teubner_conte", "conte_aeneis", 50, None),
        ("steadman", "platos-apology__apology.04jan25", 84, (0.1, 0.1, 0.9, 0.4)),
    ]
    rows = []
    for source, book, page, bbox in tests:
        r = render(source, book, page, 150, bbox)
        rows.append({"source": source, "book": book, "page": page, "bbox": bbox,
                     "bytes": r["bytes"], "cached": r["cached"], "ms": r["ms"]})
    warm = render("steadman", "platos-apology__apology.04jan25", 84, 150)
    removed = _evict()
    out = {"tests": rows, "warm_ms": warm["ms"], "evicted": removed, "cache_mb": round(sum(
        os.path.getsize(os.path.join(dp, f)) for dp, _d, fs in os.walk(CACHE) for f in fs) / 2**20, 1)}
    json.dump(out, open(os.path.join(CACHE, "page-test.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
