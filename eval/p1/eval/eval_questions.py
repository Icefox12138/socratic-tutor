import json
import os
import re
import sqlite3
import time

D = r"D:\Guo-Code\socratic-tutor\eval\p1"
DB = os.path.join(D, "ingest", "search.db")
EVAL = os.path.join(D, "eval")
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


con = sqlite3.connect(DB)
questions = json.load(open(os.path.join(EVAL, "questions.json"), encoding="utf-8"))


def search(q, topk=10):
    toks = tokens(q)
    if not toks:
        return []
    cur = con.execute(
        "SELECT c.id, c.source, c.book, c.page FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid "
        "WHERE chunks_fts MATCH ? AND c.visibility='tutor' ORDER BY bm25(chunks_fts) LIMIT ?",
        (" OR ".join(dict.fromkeys(toks)), topk))
    return cur.fetchall()


page_hits = 0
chunk_hits = 0
mrr_sum = 0.0
times = []
detail = []
for q in questions:
    t0 = time.perf_counter()
    res = search(q["question"])
    times.append((time.perf_counter() - t0) * 1000)
    rank = None
    for i, r in enumerate(res, 1):
        if r[1] == q["source"] and r[2] == q["book"] and r[3] == q["page"]:
            rank = i
            break
    page_hits += 1 if rank else 0
    chunk_hits += 1 if any(r[0] == q["chunk_id"] for r in res) else 0
    mrr_sum += (1.0 / rank) if rank else 0.0
    detail.append({"id": q["id"], "lang": q["lang"], "source": q["source"], "page_rank": rank,
                   "n": len(res), "q": q["question"][:80]})
con.close()

times.sort()
out = {
    "n": len(questions),
    "page_recall@10": round(page_hits / len(questions), 3),
    "chunk_recall@10": round(chunk_hits / len(questions), 3),
    "mrr": round(mrr_sum / len(questions), 3),
    "p95_ms": round(times[int(len(times) * 0.95) - 1], 1),
    "by_lang": {},
    "detail": detail,
}
for lang in set(q["lang"] for q in questions):
    sub = [d for d in detail if d["lang"] == lang]
    out["by_lang"][lang] = {"n": len(sub), "page_hit": sum(1 for d in sub if d["page_rank"])}
json.dump(out, open(os.path.join(EVAL, "results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "detail"}, ensure_ascii=False))
