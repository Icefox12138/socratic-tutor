"""P2 table bake-off: render candidate pages, dump ODL + PyMuPDF table structures.

Usage:
  python extract_tables.py --doc B4 --pages 337,753,777,778,780
  python extract_tables.py --doc A1 --pages 612

Outputs (eval/p2/table):
  pages/<doc>_p<page>.png          200 dpi page image (for gold annotation)
  out/<doc>_p<page>.json           both engines' tables for that page
"""
import argparse
import json
import os
import re

import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "..", "..", "p0", "catalog", "sample-manifest.json")
ODL_DIR = os.path.join(HERE, "..", "..", "p1", "bakeoff", "out", "odl-json")
PAGES = os.path.join(HERE, "pages")
OUT = os.path.join(HERE, "out")


def doc_path(doc_id):
    man = json.load(open(MANIFEST, encoding="utf-8"))
    for s in man["samples"]:
        if s["id"] == doc_id:
            return s["path"]
    raise SystemExit("unknown doc " + doc_id)


def odl_json(doc_id):
    d = os.path.join(ODL_DIR, doc_id)
    for f in os.listdir(d):
        if f.endswith(".json"):
            return json.load(open(os.path.join(d, f), encoding="utf-8"))
    raise SystemExit("no odl json in " + d)


def cell_text(node):
    out = []
    def walk(n):
        if not isinstance(n, dict):
            return
        c = n.get("content")
        if isinstance(c, str) and c.strip():
            out.append(c.strip())
        for k in n.get("kids") or []:
            walk(k)
    walk(node)
    return " ".join(out)


def odl_tables(page):
    """Tables on one PDF page, as row/col matrices plus spans."""
    tables = []
    for t in page.get("kids") or []:
        if t.get("type") != "table":
            continue
        rows = []
        for r in t.get("rows") or []:
            cells = []
            for c in r.get("cells") or []:
                cells.append({
                    "row": c.get("row number"),
                    "col": c.get("column number"),
                    "row_span": c.get("row span") or 1,
                    "col_span": c.get("column span") or 1,
                    "header": bool(c.get("is_header")),
                    "text": cell_text(c),
                })
            rows.append(cells)
        tables.append({
            "bbox": t.get("bounding box"),
            "n_rows": t.get("number of rows"),
            "n_cols": t.get("number of columns"),
            "rows": rows,
        })
    return tables


def pymupdf_tables(page):
    tables = []
    try:
        found = page.find_tables()
    except Exception as exc:  # noqa: BLE001 - report, do not abort the page
        return [{"error": str(exc)}]
    for t in found.tables:
        rows = []
        for r in t.extract():
            rows.append(["" if c is None else str(c).strip() for c in r])
        tables.append({
            "bbox": list(t.bbox),
            "n_rows": len(rows),
            "n_cols": max((len(r) for r in rows), default=0),
            "rows": rows,
            "html": t.to_html(),
        })
    return tables


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True)
    ap.add_argument("--pages", required=True)
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()

    os.makedirs(PAGES, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    pdf = doc_path(args.doc)
    odl = odl_json(args.doc)
    by_page = {}
    for t in odl.get("kids") or []:
        if t.get("type") == "table":
            by_page.setdefault(t.get("page number"), []).append(t)

    doc = pymupdf.open(pdf)
    for raw in args.pages.split(","):
        pno = int(raw)
        page = doc.load_page(pno - 1)
        png = os.path.join(PAGES, "%s_p%d.png" % (args.doc, pno))
        if not os.path.exists(png):
            page.get_pixmap(dpi=args.dpi).save(png)
        odl_here = odl_tables({"kids": by_page.get(pno, [])})
        pm_here = pymupdf_tables(page)
        rec = {"doc": args.doc, "page": pno, "png": os.path.relpath(png, HERE),
               "odl": odl_here, "pymupdf": pm_here}
        dst = os.path.join(OUT, "%s_p%d.json" % (args.doc, pno))
        json.dump(rec, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("%s p%d: odl=%d pymupdf=%d -> %s" % (args.doc, pno, len(odl_here), len(pm_here), os.path.basename(dst)))
        for t in odl_here:
            print("   odl  %dx%d bbox=%s" % (t["n_rows"], t["n_cols"], [round(x) for x in t["bbox"]]))
        for t in pm_here:
            if "error" in t:
                print("   pm   error:", t["error"])
            else:
                print("   pm   %dx%d bbox=%s" % (t["n_rows"], t["n_cols"], [round(x) for x in t["bbox"]]))
    doc.close()


if __name__ == "__main__":
    main()
