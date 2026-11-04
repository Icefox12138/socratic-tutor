import hashlib
import json
import os
import re
import sqlite3

import pymupdf

BASE = r"D:\Guo-Code"
ROOT = os.path.join(BASE, "PDF-new", "Steadman")
OUT = os.path.join(BASE, "socratic-tutor", "eval", "p1", "ingest")
os.makedirs(OUT, exist_ok=True)
DB = os.path.join(OUT, "steadman.db")

GREEK = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
CHUNK = 500
OVERLAP = 60


def sha_sample(path, size):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read(2 * 1024 * 1024))
    h.update(str(size).encode())
    return h.hexdigest()


def chunks_of(text):
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= CHUNK:
        yield text
        return
    start = 0
    while start < len(text):
        end = min(len(text), start + CHUNK)
        cut = max(text.rfind(".", start, end), text.rfind(";", start, end))
        if cut > start + CHUNK // 2:
            end = cut + 1
        yield text[start:end]
        start = max(start + 1, end - OVERLAP)


volumes = []
for lang in ("greek", "latin"):
    d = os.path.join(ROOT, lang)
    if not os.path.isdir(d):
        continue
    for fn in sorted(os.listdir(d)):
        if not fn.lower().endswith(".pdf"):
            continue
        path = os.path.join(d, fn)
        doc = pymupdf.open(path)
        pages = doc.page_count
        text_pages = 0
        chars = 0
        page_texts = []
        for i in range(pages):
            t = doc.load_page(i).get_text("text") or ""
            page_texts.append((i + 1, t))
            if len(t.strip()) >= 200:
                text_pages += 1
            chars += len(t)
        doc.close()
        share = text_pages / max(1, pages)
        volumes.append({
            "volume": fn[:-4], "lang": lang, "path": path, "pages": pages,
            "text_pages": text_pages, "chars": chars, "text_share": round(share, 3),
            "sha256": sha_sample(path, os.path.getsize(path)),
            "page_texts": page_texts,
        })

if os.path.exists(DB):
    os.remove(DB)
con = sqlite3.connect(DB)
con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, volume TEXT, lang TEXT, page INTEGER, text TEXT, visibility TEXT)")
con.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(text, tokenize='trigram')")

rows = []
for v in volumes:
    if v["text_share"] < 0.10:
        v["status"] = "excluded_low_text"
        continue
    v["status"] = "ingested"
    vis = "answer_key" if "transsheet" in v["volume"].lower() else "tutor"
    v["visibility"] = vis
    for page, text in v["page_texts"]:
        if len(text.strip()) < 200:
            continue
        for ch in chunks_of(text):
            if len(ch) >= 60:
                rows.append((v["volume"], v["lang"], page, ch, vis))
    del v["page_texts"]

con.executemany("INSERT INTO chunks (volume,lang,page,text,visibility) VALUES (?,?,?,?,?)", rows)
con.executemany("INSERT INTO chunks_fts (rowid,text) VALUES (?,?)",
                [(i + 1, r[3]) for i, r in enumerate(rows)])
con.commit()

manifest = {
    "total_volumes": len(volumes),
    "ingested": sum(1 for v in volumes if v["status"] == "ingested"),
    "excluded": sum(1 for v in volumes if v["status"] != "ingested"),
    "chunks": len(rows),
    "volumes": [{k: v[k] for k in ("volume", "lang", "pages", "text_pages", "chars", "text_share", "sha256", "status")} for v in volumes],
}
json.dump(manifest, open(os.path.join(OUT, "steadman-manifest.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)


def search(q, topk=5):
    cur = con.execute(
        "SELECT c.volume, c.lang, c.page, c.text FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid "
        "WHERE chunks_fts MATCH ? AND c.visibility='tutor' ORDER BY bm25(chunks_fts) LIMIT ?", ('"' + q.replace('"', '""') + '"', topk))
    return cur.fetchall()


tests = {
    "greek": ["Ἀπολογία", "μῆνιν", "ἄνδρα", "πόλεμος"],
    "latin": ["arma", "Dido", "Aeneas", "bellum"],
}
scores = {}
for lang, qs in tests.items():
    ok = 0
    detail = []
    for q in qs:
        res = search(q)
        hit = any(q.lower() in (r[3] or "").lower() for r in res)
        ok += 1 if hit else 0
        detail.append({"q": q, "hits": len(res), "contains": hit})
    scores[lang] = {"queries": len(qs), "hit": ok, "detail": detail}
con.close()

json.dump(scores, open(os.path.join(OUT, "steadman-queries.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(json.dumps({"volumes": manifest["total_volumes"], "ingested": manifest["ingested"],
                  "excluded": manifest["excluded"], "chunks": len(rows), "scores": scores},
                 ensure_ascii=False, indent=1))
