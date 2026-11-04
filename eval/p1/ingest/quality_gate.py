import json
import os
import random
import re
import sqlite3
import time

import pymupdf

from page_render import render, resolve

D = r"D:\Guo-Code\socratic-tutor\eval\p1\ingest"
DB = os.path.join(D, "search.db")
random.seed(42)

con = sqlite3.connect(DB)
quotas = {"steadman": 40, "library": 50, "teubner_conte": 10}
rows = []
for src, n in quotas.items():
    data = con.execute(
        "SELECT id, source, book, lang, page, text FROM chunks WHERE visibility='tutor' AND source=? "
        "ORDER BY RANDOM() LIMIT ?", (src, n)).fetchall()
    rows.extend(data)
con.close()


def norm(s):
    return re.sub(r"\s+", "", s or "")


results = []
t0 = time.perf_counter()
for i, (cid, source, book, lang, page, text) in enumerate(rows, 1):
    item = {"id": cid, "source": source, "book": book, "page": page, "ok": False}
    try:
        path = resolve(source, book)
        doc = pymupdf.open(path)
        item["pages"] = doc.page_count
        if not (1 <= page <= doc.page_count):
            item["error"] = "page_out_of_range"
            doc.close()
            results.append(item)
            continue
        page_text = doc.load_page(page - 1).get_text("text") or ""
        doc.close()
        item["chunk_match"] = norm(text)[:100] in norm(page_text)
        r = render(source, book, page, dpi=120)
        item.update({"image_bytes": r["bytes"], "cached": r["cached"], "ms": r["ms"], "ok": True})
    except Exception as e:
        item["error"] = str(e)
    results.append(item)

# S-level 20 at 200dpi
s_level = []
for item in [x for x in results if x["ok"]][:20]:
    r = render(item["source"], item["book"], item["page"], dpi=200)
    s_level.append({"id": item["id"], "bytes": r["bytes"], "cached": r["cached"], "ms": r["ms"]})

# warm cache test
warm = []
for item in [x for x in results if x["ok"]][:10]:
    r = render(item["source"], item["book"], item["page"], dpi=120)
    warm.append(r["cached"])

# canary
con = sqlite3.connect(DB)
canary = {
    "answer_key_rows": con.execute("SELECT count(*) FROM chunks WHERE visibility='answer_key'").fetchone()[0],
    "canary_text_rows": con.execute("SELECT count(*) FROM chunks WHERE text LIKE '%CANARY-7F3A%'").fetchone()[0],
    "student_text_rows": con.execute("SELECT count(*) FROM chunks WHERE visibility='tutor' AND text LIKE '%CANARY-7F3A%'").fetchone()[0],
    "student_fts_hits": con.execute(
        "SELECT count(*) FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid "
        "WHERE chunks_fts MATCH ? AND c.visibility='tutor'", ('"canary"',)).fetchone()[0],
}
con.close()

times = sorted(x["ms"] for x in results if x["ok"])
summary = {
    "sampled": len(results),
    "ok": sum(1 for x in results if x["ok"]),
    "chunk_match": sum(1 for x in results if x.get("chunk_match")),
    "p95_ms": round(times[int(len(times) * 0.95) - 1], 1) if times else None,
    "total_s": round(time.perf_counter() - t0, 1),
    "s_level": {"count": len(s_level), "all_ok": all(x["bytes"] > 0 for x in s_level)},
    "warm_cached": sum(1 for x in warm if x),
    "canary": canary,
}
json.dump({"summary": summary, "items": results, "s_level": s_level},
          open(os.path.join(D, "quality-gate.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False))
