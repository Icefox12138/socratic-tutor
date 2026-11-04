r"""Build a licence-free demo corpus the sidecar can serve end to end.

Produces:
  samples/PDF/synthetic-book.pdf   5 pages rendered from docs/assets/public/samples
  samples/search.db                chunks + FTS5 + a one-volume toc

Then:
  $env:SOCRATIC_ROOT="<repo>\samples"; $env:SOCRATIC_DB="<repo>\samples\search.db"
  uvicorn app.main:app --port 8766

  python eval/p3/make_demo_corpus.py
"""
import os
import sqlite3
import sys

import io
import re

import pymupdf
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SAMPLES = os.path.join(REPO, "docs", "assets", "public", "samples")
OUT = os.path.join(REPO, "samples")
BOOK = "synthetic-book.pdf"

PAGES = [
    ("formula.png", "zh", ["分析力学：作用量取驻值给出欧拉–拉格朗日方程。",
                           "分式、矩阵与上下标在样本页中演示。",
                           "能量守恒可由时间平移对称性导出，而非额外假设。"]),
    ("zh-horizontal.png", "zh", ["函数与极限：函数值稳定地靠近同一个数，我们就说它在该点有极限。",
                                 "极限刻画的是趋势，而不是某一点的取值。",
                                 "先给定一个正数，再要求存在另一个正数与之对应。"]),
    ("zh-vertical.png", "zh", ["學而時習之，不亦說乎；有朋自遠方來，不亦樂乎。",
                               "豎排右起，雙行小注，此為合成樣本，非真實古籍頁面。",
                               "溫故而知新，可以為師矣。"]),
    ("latin.png", "latin", ["Ars longa, vita brevis.",
                            "Omnis doctrina a quaestione incipit: quid sit, quomodo fiat, cur ita sit.",
                            "Sit tibi liber non dominus, sed comes."]),
    ("greek.png", "greek", ["ὁ ἄνθρωπος ζῷον πολιτικόν ἐστιν.",
                            "ἡ μὲν φύσις οὐδὲν μάτην ποιεῖ.",
                            "λόγος δὲ ψυχῆς ἐστιν ὁ ἑαυτὸν αὐξάνων λόγος."]),
]


def build_pdf():
    os.makedirs(os.path.join(OUT, "PDF"), exist_ok=True)
    doc = pymupdf.open()
    for name, _, _ in PAGES:
        im = Image.open(os.path.join(SAMPLES, name)).convert("RGB")
        im.thumbnail((820, 1148), Image.LANCZOS)      # 2x of the 410x574 pt page
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=82, optimize=True)
        page = doc.new_page(width=410, height=574)
        page.insert_image(page.rect, stream=buf.getvalue())
    path = os.path.join(OUT, "PDF", BOOK)
    doc.save(path)
    doc.close()
    return path


CJK = re.compile(r"[\u3400-\u9fff]+")
WORD = re.compile(r"[a-z]{2,}")


def tokens(s):
    """Same tokenisation as eval/p1/ingest/build_search.py: CJK bigrams + words."""
    out = []
    for run in CJK.findall(s):
        if len(run) == 1:
            out.append(run)
        else:
            out.extend(run[i:i + 2] for i in range(len(run) - 1))
    out.extend(WORD.findall(s.lower()))
    return out


def build_db():
    db = os.path.join(OUT, "search.db")
    if os.path.exists(db):
        os.remove(db)
    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, book TEXT, "
                "lang TEXT, page INTEGER, text TEXT, visibility TEXT)")
    con.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(text, tokenize='unicode61')")
    rows = []
    for i, (_, lang, texts) in enumerate(PAGES, 1):
        for text in texts:
            rows.append(("library", BOOK, lang, i, text, "tutor"))
    con.executemany("INSERT INTO chunks (source,book,lang,page,text,visibility) "
                    "VALUES (?,?,?,?,?,?)", rows)
    for i, row in enumerate(rows):
        con.execute("INSERT INTO chunks_fts (rowid, text) VALUES (?,?)",
                    (i + 1, " ".join(tokens(row[4]))))
    con.commit()
    con.close()

    state = os.path.join(OUT, "state.db")
    if os.path.exists(state):
        os.remove(state)
    con = sqlite3.connect(state)
    con.execute(
        "CREATE TABLE IF NOT EXISTS toc ("
        "source TEXT, book TEXT, ord INTEGER, level INTEGER, title TEXT,"
        "page_start INTEGER, page_end INTEGER, volume INTEGER, pages INTEGER,"
        "meta TEXT, PRIMARY KEY(source, book, ord))")
    con.execute(
        "INSERT INTO toc(source,book,ord,level,title,page_start,page_end,volume,pages,meta)"
        " VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("library", BOOK, 0, 1, "卷首（合成樣本）", 1, len(PAGES), None,
         len(PAGES), "{}"))
    con.commit()
    con.close()
    return db, state


def main():
    pdf = build_pdf()
    db, state = build_db()
    print("pdf  :", pdf, os.path.getsize(pdf), "bytes")
    print("db   :", db, os.path.getsize(db), "bytes")
    print("state:", state, os.path.getsize(state), "bytes")
    print()
    print("run:")
    print('  $env:SOCRATIC_ROOT="%s"' % OUT)
    print('  $env:SOCRATIC_DB="%s"' % db)
    print('  $env:SOCRATIC_STATE_DB="%s"' % state)
    print('  $env:SOCRATIC_BGE="0"')
    print("  uvicorn app.main:app --port 8766")


if __name__ == "__main__":
    sys.exit(main())
