"""Fast read-only probe of D:\\Guo-Code\\PDF using PyMuPDF."""
import csv, os, sys, time, json
import pymupdf

ROOT = r"D:\Guo-Code\PDF"
OUT = os.path.join(os.environ.get("TEMP", "."), "pdf_probe2.csv")

rows = []
for dirpath, _d, files in os.walk(ROOT):
    for fn in files:
        if fn.lower().endswith(".pdf"):
            full = os.path.join(dirpath, fn)
            rows.append(full)
rows.sort()
print(f"pdfs={len(rows)}", flush=True)

out = []
t0 = time.time()
for i, full in enumerate(rows, 1):
    rel = os.path.relpath(full, ROOT)
    cat = rel.split(os.sep)[0]
    mb = os.path.getsize(full) / 2**20
    rec = dict(cat=cat, rel=rel, mb=round(mb, 1), pages=None, cpp=None,
               imgs=None, w=None, h=None, enc=None, err="")
    try:
        doc = pymupdf.open(full)
        rec["enc"] = bool(doc.is_encrypted)
        rec["pages"] = doc.page_count
        n = min(3, doc.page_count)
        chars = 0
        imgs = 0
        for p in range(n):
            page = doc.load_page(p)
            chars += len(page.get_text("text") or "")
            imgs += len(page.get_images(full=False) or [])
        rec["cpp"] = round(chars / max(1, n), 1)
        rec["imgs"] = round(imgs / max(1, n), 2)
        r = doc.load_page(0).rect
        rec["w"], rec["h"] = round(r.width), round(r.height)
        doc.close()
    except Exception as e:  # noqa: BLE001
        rec["err"] = type(e).__name__
    out.append(rec)
    if i % 50 == 0 or i == len(rows):
        print(f"{i}/{len(rows)} {time.time()-t0:.0f}s last={rel[:60]}", flush=True)

with open(OUT, "w", newline="", encoding="utf-8-sig") as fh:
    wr = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
    wr.writeheader(); wr.writerows(out)

parsed = [o for o in out if o["pages"]]
tot_pages = sum(o["pages"] for o in parsed)
text = [o for o in parsed if (o["cpp"] or 0) >= 200]
scan = [o for o in parsed if (o["cpp"] or 0) < 50]
mid = [o for o in parsed if 50 <= (o["cpp"] or 0) < 200]
print("\n=== SUMMARY ===")
print(json.dumps({
    "files": len(out), "parsed": len(parsed), "errors": len(out) - len(parsed),
    "total_pages": tot_pages,
    "avg_pages": round(tot_pages / len(parsed), 1) if parsed else 0,
    "pages_median": sorted(o["pages"] for o in parsed)[len(parsed)//2] if parsed else 0,
    "text_pdfs": len(text), "scanned_pdfs": len(scan), "mixed_pdfs": len(mid),
    "text_pages": sum(o["pages"] for o in text),
    "scanned_pages": sum(o["pages"] for o in scan),
    "encrypted": sum(1 for o in parsed if o["enc"]),
    "elapsed_s": round(time.time()-t0, 1), "csv": OUT,
}, ensure_ascii=False, indent=2))
