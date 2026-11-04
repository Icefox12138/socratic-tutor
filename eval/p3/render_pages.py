"""Render every page of a sample book to PNG (run in .venv-bge: it has pymupdf)."""
import argparse
import json
import os
import sys

import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "..", "p0", "catalog", "sample-manifest.json")


def book_path(book_id):
    man = json.load(open(MANIFEST, encoding="utf-8"))
    for s in man["samples"]:
        if s["id"] == book_id:
            return s["path"]
    raise SystemExit("unknown book " + book_id)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--out", default=None)
    ap.add_argument("--pages", default="")
    ap.add_argument("--pdf", default="", help="explicit PDF path (for books outside the manifest)")
    args = ap.parse_args()
    out = args.out or os.path.join(HERE, "out", args.book + "_pages")
    os.makedirs(out, exist_ok=True)
    doc = pymupdf.open(args.pdf or book_path(args.book))
    wanted = []
    for part in args.pages.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            wanted.extend(range(int(a), int(b) + 1))
        else:
            wanted.append(int(part))
    wanted = wanted or list(range(1, doc.page_count + 1))
    for pno in wanted:
        dst = os.path.join(out, "%s_p%d.png" % (args.book, pno))
        if os.path.exists(dst):
            continue
        doc.load_page(pno - 1).get_pixmap(dpi=args.dpi).save(dst)
    print("rendered %d pages -> %s" % (len(wanted), out))
    doc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
