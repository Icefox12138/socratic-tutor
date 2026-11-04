"""K5 policy input: how good is the stored Greek text, and where does it come from?"""
import sqlite3

DB = r"D:\Guo-Code\socratic-tutor\eval\p1\ingest\search.db"
GREEK = lambda s: sum(1 for ch in s if "\u0370" <= ch <= "\u03ff" or "\u1f00" <= ch <= "\u1fff")
LATIN = lambda s: sum(1 for ch in s if "a" <= ch.lower() <= "z")


def main():
    con = sqlite3.connect(DB)
    con.execute("pragma temp_store=MEMORY")
    con.row_factory = sqlite3.Row
    print("langs:", [(r[0], r[1]) for r in con.execute(
        "SELECT lang, count(*) FROM chunks GROUP BY lang ORDER BY 2 DESC")])
    print("")
    print("%-8s %-46s %6s %8s %8s %8s" % ("source", "book", "chunks", "avg_len", "greek%", "latin%"))
    for r in con.execute(
        "SELECT source, book, count(*) n, avg(length(text)) L, "
        "sum(length(text)) S FROM chunks WHERE lang='greek' GROUP BY source, book ORDER BY n DESC LIMIT 10"):
        rows = con.execute("SELECT text FROM chunks WHERE lang='greek' AND source=? AND book=? LIMIT 200",
                           (r["source"], r["book"])).fetchall()
        g = sum(GREEK(x["text"]) for x in rows)
        l = sum(LATIN(x["text"]) for x in rows)
        tot = sum(max(1, len(x["text"])) for x in rows)
        print("%-8s %-46s %6d %8.0f %7.1f%% %7.1f%%" % (
            r["source"], r["book"][:46], r["n"], r["L"], 100.0 * g / tot, 100.0 * l / tot))
    print("")
    for r in con.execute("SELECT source, book, page, text FROM chunks WHERE lang='greek' LIMIT 3"):
        t = r["text"]
        print("sample %s p%d greek=%d/%d: %s" % (r["book"][:24], r["page"], GREEK(t), len(t), t[:90].replace("\n", " ")))


if __name__ == "__main__":
    main()
