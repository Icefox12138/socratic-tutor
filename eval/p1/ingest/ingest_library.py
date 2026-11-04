import csv
import hashlib
import json
import os
import re
import sqlite3

import pymupdf

BASE = r"D:\Guo-Code"
ROOT = os.path.join(BASE, "PDF")
OUT = os.path.join(BASE, "socratic-tutor", "eval", "p1", "ingest")
DB = os.path.join(OUT, "library.db")
CHUNK = 600
OVERLAP = 80
CJK = re.compile(r"[\u3400-\u9fff]")

rows_csv = list(csv.DictReader(open(os.path.join(os.environ["TEMP"], "pdf_probe2.csv"), encoding="utf-8-sig")))
books = [r for r in rows_csv if float(r["cpp"] or 0) >= 200]


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
        cut = max(text.rfind("。", start, end), text.rfind("；", start, end),
                  text.rfind(".", start, end), text.rfind(";", start, end))
        if cut > start + CHUNK // 2:
            end = cut + 1
        yield text[start:end]
        start = max(start + 1, end - OVERLAP)


if os.path.exists(DB):
    os.remove(DB)
con = sqlite3.connect(DB)
con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, book TEXT, book_id TEXT, lang TEXT, page INTEGER, text TEXT, visibility TEXT)")
con.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(text, tokenize='trigram')")

manifest = []
all_rows = []
for b in books:
    path = os.path.join(ROOT, b["rel"])
    if not os.path.exists(path):
        manifest.append({"rel": b["rel"], "status": "missing"})
        continue
    doc = pymupdf.open(path)
    pages = doc.page_count
    text_pages = 0
    chars = 0
    cjk = 0
    bid = sha_sample(path, os.path.getsize(path))[:16]
    page_texts = []
    for i in range(pages):
        t = doc.load_page(i).get_text("text") or ""
        if len(t.strip()) < 200:
            continue
        text_pages += 1
        chars += len(t)
        cjk += len(CJK.findall(t))
        page_texts.append((i + 1, t))
    doc.close()
    lang = "zh" if cjk > max(1, chars) * 0.2 else "en"
    for pno, t in page_texts:
        for ch in chunks_of(t):
            if len(ch) >= 80:
                all_rows.append((b["rel"], bid, lang, pno, ch, "tutor"))
    manifest.append({"rel": b["rel"], "pages": pages, "text_pages": text_pages,
                     "chars": chars, "book_id": bid, "lang": lang, "status": "ingested"})

con.executemany("INSERT INTO chunks (book,book_id,lang,page,text,visibility) VALUES (?,?,?,?,?,?)", all_rows)
con.executemany("INSERT INTO chunks_fts (rowid,text) VALUES (?,?)",
                [(i + 1, r[4]) for i, r in enumerate(all_rows)])
con.commit()


def search(q, topk=5):
    cur = con.execute(
        "SELECT c.book, c.lang, c.page, c.text FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid "
        "WHERE chunks_fts MATCH ? AND c.visibility='tutor' ORDER BY bm25(chunks_fts) LIMIT ?",
        ('"' + q.replace('"', '""') + '"', topk))
    return cur.fetchall()


queries = ["微分", "极限", "矩阵", "帝国主义", "剩余价值", "资本", "函数", "革命"]
qres = []
for q in queries:
    res = search(q)
    qres.append({"q": q, "hits": len(res), "contains": any(q in (r[3] or "") for r in res)})

summary = {
    "books_csv": len(books),
    "books_ingested": sum(1 for m in manifest if m["status"] == "ingested"),
    "pages": sum(m.get("pages", 0) for m in manifest),
    "text_pages": sum(m.get("text_pages", 0) for m in manifest),
    "chunks": len(all_rows),
    "queries": {"total": len(qres), "hit": sum(1 for x in qres if x["contains"]), "detail": qres},
}
json.dump({"summary": summary, "books": manifest},
          open(os.path.join(OUT, "library-manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
con.close()
print(json.dumps(summary, ensure_ascii=False, indent=1))
