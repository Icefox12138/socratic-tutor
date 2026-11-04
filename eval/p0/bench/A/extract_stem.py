import json
import os

import pymupdf

BASE = r"D:\Guo-Code"
OUT = os.path.join(BASE, "socratic-tutor", "eval", "p0", "bench", "A")
os.makedirs(os.path.join(OUT, "pages"), exist_ok=True)
manifest = json.load(open(os.path.join(BASE, "socratic-tutor", "eval", "p0", "catalog", "sample-manifest.json"), encoding="utf-8"))
samples = {s["id"]: s for s in manifest["samples"]}

report = {}
for sid in ("A1", "A2", "A3", "A4"):
    s = samples[sid]
    d = pymupdf.open(s["path"])
    start, end = s["window"]["start"], s["window"]["end"]
    stats = []
    for i in range(start, min(end + 1, d.page_count)):
        t = d.load_page(i).get_text("text") or ""
        stats.append((i, len(t)))
    # render two pages: first gold and mid window
    for tag, pno in (("gold1", s["gold_pages"][0]), ("mid", start + (end - start) // 2)):
        page = d.load_page(pno)
        pix = page.get_pixmap(dpi=120)
        pix.save(os.path.join(OUT, "pages", f"{sid}_{tag}_p{pno}.png"))
    d.close()
    lens = [n for _, n in stats]
    report[sid] = {
        "path": s["path"],
        "pages": s["pages"],
        "window": [start, end],
        "avg_chars": round(sum(lens) / max(1, len(lens)), 1),
        "zero_pages": sum(1 for n in lens if n == 0),
        "max_chars": max(lens) if lens else 0,
        "page_text": {str(p): n for p, n in stats[:5]},
    }

json.dump(report, open(os.path.join(OUT, "A-extract.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(report, ensure_ascii=False, indent=1))
