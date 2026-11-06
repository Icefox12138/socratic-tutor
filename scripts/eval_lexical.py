"""Evaluate grep vs lemma vs FTS on inflected classical forms."""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "sidecar"))

from app import config, lexical, search, translate  # noqa: E402

MODES = ("fts", "grep", "lemma", "fusion")


def load_set(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def hit_rank(results, gold):
    for rank, result in enumerate(results, 1):
        for g in gold:
            if (result.get("document_id") == g.get("document_id") and
                    result.get("section") == g.get("section")):
                return rank
    return None


def run_queries(queries, mode, k):
    config.BGE = False
    config.TRANSLATE = "off"
    config.LEXICAL = "auto" if mode == "fusion" else "off"
    translate.clear_cache()
    details = []
    for item in queries:
        started = time.perf_counter()
        if mode == "grep":
            out = lexical.grep(item["query"], limit=k)
        elif mode == "lemma":
            out = lexical.lemma_search(item["query"], limit=k)
        else:
            out = search.search(item["query"], view="student", limit=k)
        rank = hit_rank(out["results"], item["gold"])
        details.append({"id": item["id"], "query": item["query"],
                        "rank": rank, "hits": len(out["results"]),
                        "took_ms": round((time.perf_counter() - started) * 1000, 2)})
    return details


def summary(details, k):
    n = len(details) or 1
    ranks = [d["rank"] for d in details]
    return {
        "n": len(details),
        "recall@1": round(sum(1 for r in ranks if r and r <= 1) / n, 3),
        "recall@3": round(sum(1 for r in ranks if r and r <= 3) / n, 3),
        "recall@%d" % k: round(sum(1 for r in ranks if r and r <= k) / n, 3),
        "mrr@%d" % k: round(sum(1.0 / r for r in ranks if r and r <= k) / n, 3),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=os.environ.get("SOCRATIC_PUBLIC_DB")
                    or os.path.join(config.DATA, "public.db"))
    ap.add_argument("--set", default=os.path.join(HERE, "eval", "public",
                                                  "queries-lexical.jsonl"))
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    config.DB = os.path.abspath(args.db)
    config.SCHEMA = "auto"
    queries = load_set(args.set)
    report = {mode: summary(run_queries(queries, mode, args.k), args.k)
              for mode in MODES}
    if args.json:
        print(json.dumps({"db": config.DB, "set": args.set, "k": args.k,
                          "report": report}, ensure_ascii=False, indent=1))
        return 0
    print("db: %s" % config.DB)
    print("set: %s (%d queries)" % (args.set, len(queries)))
    print("| mode | n | R@1 | R@3 | R@%d | MRR@%d |" % (args.k, args.k))
    print("|---|---:|---:|---:|---:|---:|")
    for mode in MODES:
        s = report[mode]
        print("| %s | %d | %.3f | %.3f | %.3f | %.3f |" % (
            mode, s["n"], s["recall@1"], s["recall@3"],
            s["recall@%d" % args.k], s["mrr@%d" % args.k]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
