import sqlite3

con = sqlite3.connect(r"D:\Guo-Code\socratic-tutor\eval\p1\ingest\search.db")
for q in ["微分", '"微分"', "极限", "导数"]:
    try:
        n = con.execute("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH ?", (q,)).fetchone()[0]
        print(repr(q), n)
    except Exception as e:
        print(repr(q), "ERR", e)
try:
    n = con.execute(
        "SELECT count(*) FROM chunks c JOIN chunks_fts f ON c.id=f.rowid "
        "WHERE f.chunks_fts MATCH ? AND c.visibility='tutor'", ("微分",)).fetchone()[0]
    print("join", n)
except Exception as e:
    print("join ERR", e)
con.close()
