import json
import os
import statistics
import time

import requests

BASE = "http://127.0.0.1:8765"
QFILE = r"D:\Guo-Code\socratic-tutor\eval\p1\eval\questions.json"


def main():
    qs = json.load(open(QFILE, encoding="utf-8"))
    hits = 0
    by = {}
    lat = []
    detail = []
    for q in qs:
        t0 = time.perf_counter()
        r = requests.get(BASE + "/v1/search", params={
            "q": q["question"], "view": "student", "limit": 10}, timeout=120)
        lat.append((time.perf_counter() - t0) * 1000)
        res = r.json().get("results", []) if r.ok else []
        hit = any(x["source"] == q["source"] and x["book"] == q["book"]
                  and x["page"] == q["page"] for x in res)
        hits += 1 if hit else 0
        by.setdefault(q["lang"], [0, 0])
        by[q["lang"]][0] += 1
        by[q["lang"]][1] += 1 if hit else 0
        detail.append({"id": q["id"], "lang": q["lang"], "hit": hit,
                       "n": len(res), "status": r.status_code,
                       "mode": r.json().get("mode") if r.ok else None})
    lat.sort()
    out = {
        "n": len(qs),
        "page_recall@10": round(hits / len(qs), 3),
        "by_lang": {k: {"n": v[0], "hit": v[1]} for k, v in by.items()},
        "p50_ms": round(statistics.median(lat), 1),
        "p95_ms": round(lat[int(len(lat) * 0.95) - 1], 1),
        "detail": detail,
    }
    json.dump(out, open(os.path.join(os.path.dirname(__file__), "eval-sidecar.json"),
                        "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "detail"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
