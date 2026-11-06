import os
import sqlite3

DB = os.environ.get(
    "SOCRATIC_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "samples", "search.db"))
con = sqlite3.connect(DB)
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
