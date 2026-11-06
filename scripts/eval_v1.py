"""Evaluate the v1 (private PDF) retrieval path on the P1 100-question set."""
import argparse
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "sidecar"))
ROOT = os.path.dirname(HERE)

from app import config, search, translate  # noqa: E402

MODES = {
    "fts": {"bge": False, "translate": "off", "lexical": "off", "enh": False},
    "bge": {"bge": True, "translate": "off", "lexical": "off", "enh": False},
    "bge+tr": {"bge": True, "translate": "glossary", "lexical": "off", "enh": True},
    "bge+llm": {"bge": True, "translate": "llm", "lexical": "off", "enh": True},
    "bge+llm+rr": {"bge": True, "translate": "llm", "lexical": "off", "enh": True,
                   "final_rerank": True},
    "bge+llm+wide": {"bge": True, "translate": "llm", "lexical": "off",
                     "enh": True, "wide": True},
    "bge+dedupe": {"bge": True, "translate": "off", "lexical": "off", "enh": True},
    "bge+wide": {"bge": True, "translate": "off", "lexical": "off", "enh": True,
                 "wide": True},
    "bge+w2": {"bge": True, "translate": "off", "lexical": "off", "enh": True,
               "bge_weight": 2.0},
    "bge+lex": {"bge": True, "translate": "off", "lexical": "auto", "enh": True},
    "bge+both": {"bge": True, "translate": "glossary", "lexical": "auto", "enh": True},
}


def load_questions(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def hit_rank(results, q):
    for rank, result in enumerate(results, 1):
        if (result.get("source") == q["source"] and
                result.get("book") == q["book"] and
                result.get("page") == q["page"]):
            return rank
    return None


def run(questions, mode, k):
    cfg = MODES[mode]
    config.BGE = cfg["bge"]
    config.TRANSLATE = cfg["translate"]
    config.LEXICAL = cfg["lexical"]
    config.V1_RETRIEVAL = cfg["enh"]
    config.V1_FINAL_RERANK = cfg.get("final_rerank", False)
    config.BGE_TOPK = 100 if cfg.get("wide") else 50
    config.RERANK_TOPK = 100 if cfg.get("wide") else 50
    config.BGE_RRF_WEIGHT = cfg.get("bge_weight", 1.0)
    translate.clear_cache()
    details = []
    for q in questions:
        started = time.perf_counter()
        out = search.search(q["question"], view="tutor", limit=k)
        rank = hit_rank(out["results"], q)
        details.append({"id": q["id"], "lang": q["lang"], "rank": rank,
                        "n": len(out["results"]),
                        "took_ms": round((time.perf_counter() - started) * 1000, 2)})
    return details


def summary(details, k):
    n = len(details) or 1
    ranks = [d["rank"] for d in details]
    by = {}
    for d in details:
        by.setdefault(d["lang"], []).append(d["rank"])
    by_lang = {}
    for lang, rs in sorted(by.items()):
        m = len(rs) or 1
        by_lang[lang] = {
            "n": len(rs),
            "recall@1": round(sum(1 for r in rs if r and r <= 1) / m, 3),
            "recall@%d" % k: round(sum(1 for r in rs if r and r <= k) / m, 3),
        }
    return {
        "n": len(details),
        "recall@1": round(sum(1 for r in ranks if r and r <= 1) / n, 3),
        "recall@3": round(sum(1 for r in ranks if r and r <= 3) / n, 3),
        "recall@%d" % k: round(sum(1 for r in ranks if r and r <= k) / n, 3),
        "mrr@%d" % k: round(sum(1.0 / r for r in ranks if r and r <= k) / n, 3),
        "median_ms": round(statistics.median([d["took_ms"] for d in details]), 1),
        "by_lang": by_lang,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=os.environ.get("SOCRATIC_V1_DB"))
    ap.add_argument("--vectors", default=os.environ.get("SOCRATIC_BGE_VECTORS"))
    ap.add_argument("--ids", default=os.environ.get("SOCRATIC_BGE_IDS"))
    ap.add_argument("--questions", default=os.path.join(
        ROOT, "rag-build", "eval", "p1", "eval", "questions.json"))
    ap.add_argument("--modes", default="fts,bge")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not args.db:
        raise SystemExit("--db or SOCRATIC_V1_DB is required")
    config.DB = os.path.abspath(args.db)
    config.SCHEMA = "v1"
    if args.vectors:
        config.BGE_VECTORS = args.vectors
    if args.ids:
        config.BGE_IDS = args.ids
    questions = load_questions(args.questions)
    report = {}
    for mode in [m.strip() for m in args.modes.split(",") if m.strip()]:
        report[mode] = summary(run(questions, mode, args.k), args.k)
    if args.json:
        print(json.dumps({"db": config.DB, "questions": args.questions,
                          "report": report}, ensure_ascii=False, indent=1))
        return 0
    print("db: %s" % config.DB)
    print("questions: %s (%d)" % (args.questions, len(questions)))
    print("| mode | n | R@1 | R@3 | R@%d | MRR@%d | median ms |" % (args.k, args.k))
    print("|---|---:|---:|---:|---:|---:|---:|")
    for mode, s in report.items():
        print("| %s | %d | %.3f | %.3f | %.3f | %.3f | %.1f |" % (
            mode, s["n"], s["recall@1"], s["recall@3"],
            s["recall@%d" % args.k], s["mrr@%d" % args.k], s["median_ms"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
