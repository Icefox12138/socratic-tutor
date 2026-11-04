import json
import os
import re
import sqlite3
import time

import pymupdf

BASE = r"D:\Guo-Code"
D = os.path.join(BASE, "socratic-tutor", "eval", "p1", "ingest")
DB = os.path.join(D, "search.db")
CJK = re.compile(r"[\u3400-\u9fff]+")
WORD = re.compile(r"[a-z]{2,}")


def tokens(s):
    out = []
    for run in CJK.findall(s):
        if len(run) == 1:
            out.append(run)
        else:
            out.extend(run[i:i + 2] for i in range(len(run) - 1))
    out.extend(WORD.findall(s.lower()))
    return out


if os.path.exists(DB):
    os.remove(DB)
con = sqlite3.connect(DB)
con.execute("PRAGMA journal_mode=WAL")
con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, book TEXT, lang TEXT, page INTEGER, text TEXT, visibility TEXT)")
con.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(text, tokenize='unicode61')")

rows = []
for src_db, source in ((os.path.join(D, "steadman.db"), "steadman"),
                       (os.path.join(D, "library.db"), "library")):
    c = sqlite3.connect(src_db)
    if source == "steadman":
        data = c.execute("SELECT volume, lang, page, text, visibility FROM chunks").fetchall()
    else:
        data = c.execute("SELECT book, lang, page, text, visibility FROM chunks").fetchall()
    rows.extend((source, b, l, p, t, v) for b, l, p, t, v in data)
    c.close()

# Teubner Conte: text-layer, latin
doc = pymupdf.open(os.path.join(BASE, "teubner", "conte_aeneis.pdf"))
for i in range(doc.page_count):
    t = doc.load_page(i).get_text("text") or ""
    if len(t.strip()) >= 200:
        for k in range(0, len(t), 500):
            ch = t[k:k + 500]
            if len(ch) >= 80:
                rows.append(("teubner_conte", "conte_aeneis", "latin", i + 1, ch, "tutor"))
doc.close()

rows.append(("canary", "canary", "zh", 1, "CANARY-7F3A answer key: 项羽不杀刘邦的最终答案是成本收益。", "answer_key"))

con.executemany("INSERT INTO chunks (source,book,lang,page,text,visibility) VALUES (?,?,?,?,?,?)", rows)
con.executemany("INSERT INTO chunks_fts (rowid,text) VALUES (?,?)",
                [(i + 1, " ".join(tokens(r[4]))) for i, r in enumerate(rows)])
con.commit()
print("rows", len(rows), flush=True)

QUERIES = [("princeton", "导数"), ("princeton", "极限"), ("princeton", "泰勒"), ("princeton", "积分"),
           ("conte", "arma"), ("conte", "Dido"), ("conte", "Aeneas"), ("conte", "Juno"),
           ("lenin2", "帝国主义"), ("lenin2", "无产阶级"), ("lenin2", "土地"), ("lenin2", "革命"),
           ("capital", "剩余价值"), ("capital", "商品"), ("capital", "货币"), ("capital", "资本"),
           ("vergil", "Aeneas"), ("vergil", "Juno"), ("vergil", "Dido"), ("vergil", "Carthage")]


def search(q, topk=10):
    cur = con.execute(
        "SELECT c.id, c.text FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid "
        "WHERE chunks_fts MATCH ? AND c.visibility='tutor' ORDER BY bm25(chunks_fts) LIMIT ?",
        ('"' + " ".join(tokens(q)) + '"', topk))
    return cur.fetchall()


hits = 0
times = []
detail = []
for book, q in QUERIES:
    t0 = time.perf_counter()
    res = search(q)
    times.append((time.perf_counter() - t0) * 1000)
    ok = any(q.lower() in (r[1] or "").lower() for r in res)
    hits += 1 if ok else 0
    detail.append({"book": book, "q": q, "hit": ok, "n": len(res)})

times.sort()
canary = search("CANARY-7F3A", 5)
out = {
    "chunks": len(rows),
    "queries": len(QUERIES),
    "recall@10": round(hits / len(QUERIES), 3),
    "p95_ms": round(times[int(len(times) * 0.95) - 1], 1),
    "mean_ms": round(sum(times) / len(times), 1),
    "canary_student_hits": sum(1 for r in canary if "CANARY" in r[1]),
    "detail": detail,
}
json.dump(out, open(os.path.join(D, "search-eval.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "detail"}, ensure_ascii=False))
con.close()
