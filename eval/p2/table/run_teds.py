"""Score ODL vs PyMuPDF table extraction against hand-built gold tables.

  python run_teds.py

Gold: eval/p2/table/gold/<doc>_p<page>.html (hand transcription from pages/*.png).
Engine output: eval/p2/table/out/<doc>_p<page>.json (extract_tables.py).

A page may make an engine emit several tables; the one used is the best match
for the gold on that page, and the chosen index is reported so the pick can be
audited.
"""
import json
import os
import sys

import teds as T

HERE = os.path.dirname(os.path.abspath(__file__))
GOLD = os.path.join(HERE, "gold")
OUT = os.path.join(HERE, "out")

# text_scored=False: the gold cell text is a lossy transcription (formulas,
# superscripts, column-line breaks), so only the structure is comparable.
CASES = [
    {"doc": "B4", "page": 337, "text_scored": True,
     "note": "9 行 6 列统计表；ODL 把整列数据并进一行"},
    {"doc": "B4", "page": 780, "text_scored": True,
     "note": "两级表头（1864/1865 年各 2 列）+ 9 行"},
    {"doc": "B4", "page": 777, "text_scored": True,
     "note": "同页 3 表，金标取中间 3x4（马/牛/羊/猪）"},
    {"doc": "A1", "page": 612, "text_scored": False,
     "note": "5x2 公式表；单元格是多行公式，文本不可逐字重建"},
]


def engine_trees(record):
    out = {}
    odl = [T.odl_to_tree(t) for t in record.get("odl") or []]
    pm = [T.grid_to_tree(t.get("rows") or []) for t in record.get("pymupdf") or [] if "rows" in t]
    out["odl"] = odl
    out["pymupdf"] = pm
    return out


def best(gold_root, trees):
    scored = []
    for i, tr in enumerate(trees):
        scored.append((T.similarity(gold_root, tr), T.similarity(gold_root, tr, struct=True), i))
    if not scored:
        return 0.0, 0.0, -1
    scored.sort(reverse=True)
    return scored[0]


def main():
    rows = []
    for case in CASES:
        key = "%s_p%d" % (case["doc"], case["page"])
        gold_path = os.path.join(GOLD, key + ".html")
        out_path = os.path.join(OUT, key + ".json")
        if not (os.path.exists(gold_path) and os.path.exists(out_path)):
            print("skip " + key + " (missing gold or engine output)")
            continue
        gold_root = T.parse_html(open(gold_path, encoding="utf-8").read())
        record = json.load(open(out_path, encoding="utf-8"))
        trees = engine_trees(record)
        row = {"case": key, "page": case["page"], "doc": case["doc"],
               "text_scored": case["text_scored"], "note": case["note"],
               "gold_nodes": T.tree_size(gold_root),
               "gold_rows": len(gold_root.children),
               "gold_cols": max((len(r.children) for r in gold_root.children), default=0)}
        for eng in ("odl", "pymupdf"):
            text, struct, idx = best(gold_root, trees[eng])
            pred = trees[eng][idx] if idx >= 0 else None
            row[eng] = {"teds": round(text, 4), "teds_struct": round(struct, 4),
                        "index": idx, "tables": len(trees[eng]),
                        "nodes": T.tree_size(pred) if pred else 0,
                        "rows": len(pred.children) if pred else 0,
                        "cols": max((len(r.children) for r in pred.children), default=0) if pred else 0,
                        "shape": "%dx%d" % (len(pred.children), max((len(r.children) for r in pred.children), default=0)) if pred else "-"}
        rows.append(row)
        print("%-9s gold=%dx%d | odl %s teds=%.3f struct=%.3f (t#%d) | pymupdf %s teds=%.3f struct=%.3f (t#%d)"
              % (key, row["gold_rows"], row["gold_cols"],
                 row["odl"]["shape"], row["odl"]["teds"], row["odl"]["teds_struct"], row["odl"]["index"],
                 row["pymupdf"]["shape"], row["pymupdf"]["teds"], row["pymupdf"]["teds_struct"], row["pymupdf"]["index"]))

    text_rows = [r for r in rows if r["text_scored"]]
    mean = lambda rs, eng, field: (sum(r[eng][field] for r in rs) / len(rs)) if rs else None
    summary = {
        "cases": rows,
        "mean_teds_struct_all": {eng: round(mean(rows, eng, "teds_struct"), 4) for eng in ("odl", "pymupdf")},
        "mean_teds_text_scored": {eng: round(mean(text_rows, eng, "teds"), 4) for eng in ("odl", "pymupdf")},
        "n_cases": len(rows),
        "n_text_scored": len(text_rows),
    }
    dst = os.path.join(HERE, "teds-results.json")
    json.dump(summary, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("")
    print("mean TEDS (text)   odl=%.3f  pymupdf=%.3f  over %d cases"
          % (summary["mean_teds_text_scored"]["odl"], summary["mean_teds_text_scored"]["pymupdf"], len(text_rows)))
    print("mean TEDS (struct) odl=%.3f  pymupdf=%.3f  over %d cases"
          % (summary["mean_teds_struct_all"]["odl"], summary["mean_teds_struct_all"]["pymupdf"], len(rows)))
    print("-> " + dst)


if __name__ == "__main__":
    sys.exit(main())
