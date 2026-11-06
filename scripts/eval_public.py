"""Evaluate public-corpus retrieval on a JSONL gold set.

    python scripts/eval_public.py --db data/public.db --modes fts,fts+tr,bge,bge+tr
    python scripts/eval_public.py --modes fts,bge,bge+tr,bge+llm --json

Each line of the set is ``{id, subset, query, gold:[{document_id, section}]}``.
A query is a hit when any top-k result matches one gold entry exactly.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "sidecar"))

from app import config, search, translate  # noqa: E402

MODES = {
    "fts": {"bge": False, "translate": "off"},
    "fts+tr": {"bge": False, "translate": "glossary"},
    "bge": {"bge": True, "translate": "off"},
    "bge+tr": {"bge": True, "translate": "glossary"},
    "fts+auto": {"bge": False, "translate": "auto"},
    "bge+auto": {"bge": True, "translate": "auto"},
    "bge+auto+lex": {"bge": True, "translate": "auto", "lexical": "auto"},
    "bge+tr+lex": {"bge": True, "translate": "glossary", "lexical": "auto"},
    "fts+llm": {"bge": False, "translate": "llm"},
    "bge+llm": {"bge": True, "translate": "llm"},
}


def load_set(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            rows.append(json.loads(line))
    return rows


def hit_rank(results, gold):
    for rank, result in enumerate(results, 1):
        for g in gold:
            if (result.get("document_id") == g.get("document_id") and
                    result.get("section") == g.get("section")):
                return rank
    return None


def _summary(details, k):
    n = len(details) or 1
    ranks = [d["rank"] for d in details]
    return {
        "n": len(details),
        "recall@1": round(sum(1 for r in ranks if r and r <= 1) / n, 3),
        "recall@3": round(sum(1 for r in ranks if r and r <= 3) / n, 3),
        "recall@%d" % k: round(sum(1 for r in ranks if r and r <= k) / n, 3),
        "mrr@%d" % k: round(sum(1.0 / r for r in ranks if r and r <= k) / n, 3),
    }


def run_mode(queries, mode_name, k):
    mode = MODES[mode_name]
    config.BGE = mode["bge"]
    config.TRANSLATE = mode["translate"]
    config.LEXICAL = mode.get("lexical", "off")
    translate.clear_cache()
    details = []
    for item in queries:
        started = time.perf_counter()
        out = search.search(item["query"], view="student", limit=k)
        rank = hit_rank(out["results"], item["gold"])
        first = out["results"][0] if out["results"] else None
        details.append({
            "id": item["id"], "subset": item.get("subset", "all"),
            "query": item["query"], "rank": rank,
            "actual_mode": out.get("mode"), "translated": out.get("translated", False),
            "hits": len(out["results"]),
            "first": ({"document_id": first["document_id"],
                       "section": first.get("section"),
                       "text": (first.get("text") or "")[:80]}
                      if first else None),
            "took_ms": round((time.perf_counter() - started) * 1000, 1),
        })
    return details


def _print_table(report, k):
    print("| mode | n | R@1 | R@3 | R@%d | MRR@%d |" % (k, k))
    print("|---|---:|---:|---:|---:|---:|")
    for mode, data in report.items():
        s = data["overall"]
        print("| %s | %d | %.3f | %.3f | %.3f | %.3f |" % (
            mode, s["n"], s["recall@1"], s["recall@3"],
            s["recall@%d" % k], s["mrr@%d" % k]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=os.environ.get("SOCRATIC_PUBLIC_DB")
                    or os.path.join(config.DATA, "public.db"))
    ap.add_argument("--set", default=os.path.join(HERE, "eval", "public",
                                                  "queries-human.jsonl"))
    ap.add_argument("--modes", default="fts,fts+tr,bge,bge+tr",
                    help="comma-separated: " + ", ".join(MODES))
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--show-misses", action="store_true")
    args = ap.parse_args(argv)

    config.DB = os.path.abspath(args.db)
    config.SCHEMA = "auto"
    queries = load_set(args.set)
    if not queries:
        raise SystemExit("empty set: %s" % args.set)

    names = [m.strip() for m in args.modes.split(",") if m.strip()]
    if "bge+llm" in names and not translate._key():
        print("skip bge+llm: no LLM key configured", file=sys.stderr)
        names = [m for m in names if m != "bge+llm"]

    report, all_details = {}, {}
    for name in names:
        if name not in MODES:
            raise SystemExit("unknown mode %r" % name)
        details = run_mode(queries, name, args.k)
        all_details[name] = details
        if MODES[name]["bge"] and not any(
                str(d.get("actual_mode") or "").startswith("bge") for d in details):
            print("warning: %s requested BGE but the service fell back to FTS "
                  "(missing vectors or model)" % name, file=sys.stderr)
        subsets = {}
        for item in details:
            subsets.setdefault(item["subset"], []).append(item)
        report[name] = {
            "overall": _summary(details, args.k),
            "subsets": {s: _summary(d, args.k) for s, d in subsets.items()},
        }

    if args.json:
        print(json.dumps({"db": config.DB, "set": args.set, "k": args.k,
                          "report": report, "details": all_details},
                         ensure_ascii=False, indent=1))
        return 0

    print("db: %s" % config.DB)
    print("set: %s (%d queries)" % (args.set, len(queries)))
    _print_table(report, args.k)
    print()
    print("| subset | " + " | ".join(names) + " |")
    print("|---|" + "---:|" * len(names))
    subsets = sorted({q.get("subset", "all") for q in queries})
    for subset in subsets:
        cells = []
        for name in names:
            s = report[name]["subsets"].get(subset)
            cells.append("%.3f" % s["recall@%d" % args.k] if s else "-")
        print("| %s | %s |" % (subset, " | ".join(cells)))

    if args.show_misses:
        print()
        for name in names:
            misses = [d for d in all_details[name] if not d["rank"]]
            if not misses:
                continue
            print("## %s misses (%d)" % (name, len(misses)))
            for d in misses:
                first = d["first"] or {}
                print("- %s [%s] %r -> %s / %s" % (
                    d["id"], d["subset"], d["query"],
                    first.get("document_id"), first.get("section")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
