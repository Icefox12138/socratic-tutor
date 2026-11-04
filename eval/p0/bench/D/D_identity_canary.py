import csv
import json
import os
import sqlite3

BASE = r"D:\Guo-Code"
D = os.path.join(BASE, "socratic-tutor", "eval", "p0", "bench", "D")
ID = os.path.join(BASE, "socratic-tutor", "eval", "p0", "identity")
os.makedirs(ID, exist_ok=True)

cat = {}
for line in open(os.path.join(BASE, "socratic-tutor", "eval", "p0", "catalog", "catalog.jsonl"), encoding="utf-8"):
    m = json.loads(line)
    cat[(m["root"], m["rel"])] = m

rows = [
    {"id": "L036", "l_number": "L036", "title": "Plato: Euthyphro, Apology, Crito, Phaedo, Phaedrus",
     "edition_year": "1914 (Loeb; reprint)", "file": "loeb/greek_L036_plato.pdf",
     "sha256": cat[("loeb", "greek_L036_plato.pdf")]["sha256"], "pages": 601, "verdict": "identity_ok"},
    {"id": "L063N", "l_number": "L063N", "title": "Virgil: Aeneid I-VI (revised)",
     "edition_year": "1916 (MCMXVI)", "file": "loeb/latin_L063N_vergil.pdf",
     "sha256": cat[("loeb", "latin_L063N_vergil.pdf")]["sha256"], "pages": 576, "verdict": "identity_ok"},
    {"id": "K7", "l_number": "Teubner", "title": "P. Vergili Maronis Aeneis (Conte)",
     "edition_year": "2009", "file": "teubner/conte_aeneis.pdf",
     "sha256": cat[("teubner", "conte_aeneis.pdf")]["sha256"], "pages": 434, "verdict": "identity_ok"},
    {"id": "K8", "l_number": "Teubner", "title": "Homerus: Ilias (West), vol. I",
     "edition_year": "1998", "file": "teubner/west_ilias1.pdf",
     "sha256": cat[("teubner", "west_ilias1.pdf")]["sha256"], "pages": 432, "verdict": "identity_ok"},
]
with open(os.path.join(ID, "loeb-teubner.csv"), "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

# canary tests on D4 index
db = os.path.join(BASE, "socratic-tutor", "eval", "p0", "retrieval", "index.db")
con = sqlite3.connect(db)
q = '"CANARY-7F3A"'


def count(view):
    cur = con.execute(
        "SELECT count(*) FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid "
        "WHERE chunks_fts MATCH ? AND (?='answer_key' OR c.visibility!='answer_key')", (q, view))
    return cur.fetchone()[0]


res = {
    "total_chunks": con.execute("SELECT count(*) FROM chunks").fetchone()[0],
    "canary_rows": con.execute("SELECT count(*) FROM chunks WHERE text LIKE '%CANARY-7F3A%'").fetchone()[0],
    "view_student_hits": count("student"),
    "view_tutor_hits": count("tutor"),
    "view_answer_key_hits": count("answer_key"),
    "sql_unfiltered_hits": con.execute("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH ?", (q,)).fetchone()[0],
}
con.close()
json.dump(res, open(os.path.join(D, "D-canary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False))
