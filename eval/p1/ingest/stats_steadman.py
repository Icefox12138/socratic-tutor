import json
import os
import sqlite3

con = sqlite3.connect(r"D:\Guo-Code\socratic-tutor\eval\p1\ingest\steadman.db")
print("db MB", round(os.path.getsize(r"D:\Guo-Code\socratic-tutor\eval\p1\ingest\steadman.db") / 2**20, 1))
print("by visibility", con.execute("SELECT visibility, count(*) FROM chunks GROUP BY visibility").fetchall())
print("trans volumes", con.execute("SELECT count(DISTINCT volume) FROM chunks WHERE visibility='answer_key'").fetchone()[0])
print("pages", con.execute("SELECT count(*) FROM (SELECT DISTINCT volume, page FROM chunks)").fetchone()[0])
con.close()
q = json.load(open(r"D:\Guo-Code\socratic-tutor\eval\p1\ingest\steadman-queries.json", encoding="utf-8"))
print("queries", {k: (v["hit"], v["queries"]) for k, v in q.items()})
