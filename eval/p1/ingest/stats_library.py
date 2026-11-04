import json
import os
import sqlite3

D = r"D:\Guo-Code\socratic-tutor\eval\p1\ingest"
con = sqlite3.connect(os.path.join(D, "library.db"))
print("db MB", round(os.path.getsize(os.path.join(D, "library.db")) / 2**20, 1))
print("chunks", con.execute("SELECT count(*) FROM chunks").fetchone()[0])
print("by lang", con.execute("SELECT lang, count(*) FROM chunks GROUP BY lang").fetchall())
print("books", con.execute("SELECT count(DISTINCT book) FROM chunks").fetchone()[0])
con.close()
m = json.load(open(os.path.join(D, "library-manifest.json"), encoding="utf-8"))
print("manifest books", m["summary"]["books_ingested"], "text_pages", m["summary"]["text_pages"])
print("langs", {l: sum(1 for b in m["books"] if b.get("lang") == l) for l in ("zh", "en")})
