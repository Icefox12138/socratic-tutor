import json
import os
import sqlite3

DB = os.path.join(r"D:\Guo-Code\socratic-tutor\eval\p1\ingest", "library.db")
con = sqlite3.connect(DB)


def search(q, topk=5):
    if len(q) >= 3:
        cur = con.execute(
            "SELECT c.book, c.lang, c.page, c.text FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid "
            "WHERE chunks_fts MATCH ? AND c.visibility='tutor' ORDER BY bm25(chunks_fts) LIMIT ?",
            ('"' + q.replace('"', '""') + '"', topk))
    else:
        cur = con.execute(
            "SELECT book, lang, page, text FROM chunks WHERE visibility='tutor' AND text LIKE ? LIMIT ?",
            ("%" + q + "%", topk))
    return cur.fetchall()


queries = ["微分", "极限", "矩阵", "函数", "资本", "革命", "帝国主义", "剩余价值", "导数", "商品"]
rows = []
for q in queries:
    res = search(q)
    rows.append({"q": q, "len": len(q), "hits": len(res),
                 "contains": any(q in (r[3] or "") for r in res),
                 "top": [(r[0][:40], r[2]) for r in res[:2]]})

out = {"total": len(rows), "hit": sum(1 for r in rows if r["contains"]), "rows": rows}
json.dump(out, open(os.path.join(os.path.dirname(DB), "library-queries.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
con.close()
print(json.dumps({"total": out["total"], "hit": out["hit"]}, ensure_ascii=False))
