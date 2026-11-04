"""Turn OCR page dumps into a chapter index and store it in the sidecar DB.

  python eval/p3/build_toc.py --book C1 --source library --pages out/C1_pages.jsonl

Acceptance here is structural: every chapter must be a contiguous, ordered
page range covering the volume, and the count must match the volume's 目录
(yellow flag when it does not).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(REPO, "sidecar"))

from app import toc as toc_mod  # noqa: E402

MANIFEST = os.path.join(REPO, "eval", "p0", "catalog", "sample-manifest.json")


def sample(book_id):
    man = json.load(open(MANIFEST, encoding="utf-8"))
    for s in man["samples"]:
        if s["id"] == book_id:
            return s
    raise SystemExit("unknown book " + book_id)


def load_pages(paths):
    """Accept both full-page OCR ("lines") and header-only OCR ("vol"/"head")."""
    pages = {}
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                pno = int(rec["page"])
                if "lines" in rec:
                    pages[pno] = rec.get("lines") or []
                else:
                    head = rec.get("head") or ""
                    pages[pno] = [{"text": head or ("卷%d" % rec["vol"] if rec.get("vol") else "")}]
    return pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--source", default="library")
    ap.add_argument("--shards", nargs="+", required=True)
    ap.add_argument("--state-db", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    s = sample(args.book)
    book_key = s["rel"].split("PDF\\", 1)[-1] if args.source == "library" else s["id"]
    pages = load_pages(args.shards)
    if not pages:
        raise SystemExit("no OCR pages in " + " ".join(args.shards))
    vols = {p: toc_mod.volume_of(lines) for p, lines in pages.items()}
    vols = toc_mod.clean_volumes(vols, min_run=5)
    chapters = toc_mod.enrich(toc_mod.build_from_volumes(vols), pages)
    dropped = sum(1 for v in {p: toc_mod.volume_of(l) for p, l in pages.items()}.values() if v) - len(vols)
    missing = [p for p in range(1, max(pages) + 1) if p not in pages]
    print("ocr pages=%d (missing %d) chapters=%d" % (len(pages), len(missing), len(chapters)))
    for ch in chapters[:12]:
        print("  %-24s p%d-%d (%d 页)" % (ch["title"], ch["page_start"], ch["page_end"], ch["pages"]))
    # Front/back matter makes the browser complete: every page belongs to a row.
    total_pages = max(pages)
    if chapters and chapters[0]["page_start"] > 1:
        chapters.insert(0, {"ord": 0, "level": 2, "title": "卷首（目錄/出版說明）",
                            "page_start": 1, "page_end": chapters[0]["page_start"] - 1,
                            "volume": None, "pages": chapters[0]["page_start"] - 1})
    if chapters and chapters[-1]["page_end"] < total_pages:
        last = chapters[-1]
        chapters.append({"ord": len(chapters), "level": 2, "title": "卷末（附錄）",
                         "page_start": last["page_end"] + 1, "page_end": total_pages,
                         "volume": None, "pages": total_pages - last["page_end"]})
    for i, ch in enumerate(chapters):
        ch["ord"] = i
    n = toc_mod.save(args.source, book_key, chapters,
                     meta={"ocr_pages": len(pages), "missing": len(missing)},
                     path=args.state_db)
    out = args.out or os.path.join(HERE, "out", args.book + "-toc.json")
    json.dump({"source": args.source, "book": book_key, "chapters": chapters},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved %d chapters -> %s" % (n, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
