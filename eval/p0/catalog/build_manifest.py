import glob, hashlib, json, os

import pymupdf

BASE = r"D:\Guo-Code"
OUT = os.path.join(BASE, "socratic-tutor", "eval", "p0", "catalog")
os.makedirs(OUT, exist_ok=True)


def sha_sample(path, size):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read(4 * 1024 * 1024))
        if size > 8 * 1024 * 1024:
            fh.seek(-4 * 1024 * 1024, os.SEEK_END)
            h.update(fh.read(4 * 1024 * 1024))
    h.update(str(size).encode())
    return h.hexdigest()


SPECS = [
    # id, branch, type, pattern, keyword, window, target phrase, start override
    ("A1", "stem", "deep", r"PDF/数学/**/*Princeton calculus Reader*.pdf", None, 60, None, None),
    ("A2", "stem", "deep", r"PDF/数学/**/*线性代数 _ 数学专业用*.pdf", None, 60, None, None),
    ("A3", "stem", "smoke", r"PDF/计算机/**/*Primer C++*.pdf", None, 30, None, None),
    ("A4", "stem", "smoke", r"PDF/物理/伯克利物理学教程/*第1卷*.pdf", None, 30, None, None),
    ("B1", "zh-modern", "deep", r"PDF/马列主义/**/*列宁选集第二卷*.pdf", None, 60, None, None),
    ("B2", "zh-modern", "deep", r"PDF/西方文史哲/**/*理想国*.pdf", None, 60, None, None),
    ("B3", "zh-modern", "smoke", r"PDF/中国文史哲/鲁迅全集/*01*.pdf", None, 30, None, None),
    ("B4", "zh-modern", "smoke", r"PDF/马列主义/**/*资本论第一卷*.pdf", None, 30, None, None),
    ("C1", "zh-vertical", "deep", r"PDF/中国文史哲/二十四史*/**/01001*.pdf", None, 60, None, None),
    ("C2", "zh-vertical", "deep", r"PDF/中国文史哲/十三经注疏/01*.pdf", None, 60, None, None),
    ("C3", "zh-vertical", "smoke", r"PDF/中国文史哲/资治通鉴中华书局点校本/**/*.pdf", "01.", 30, None, None),
    ("C4", "zh-vertical", "smoke", r"PDF/中国文史哲/金庸*/**/*01*.pdf", "作品集01", 30, None, None),
    ("K1", "classics", "deep", r"PDF-new/Steadman/greek/platos-apology__*.pdf", "apology.04", 60, None, None),
    ("K2", "classics", "deep", r"PDF-new/Steadman/latin/ap-vergil-usa__collegevergil*.pdf", "04jan25", 60, None, None),
    ("K3", "classics", "smoke", r"PDF-new/Steadman/greek/files-herodotus__hero*.pdf", None, 30, None, None),
    ("K4", "classics", "smoke", r"PDF-new/Steadman/latin/livy__Livy*.pdf", None, 30, None, None),
    ("K5", "classics", "smoke", r"loeb/greek_L036_plato.pdf", None, 30, "ΑΠΟΛΟΓΙΑ", 82),
    ("K6", "classics", "smoke", r"loeb/latin_L063N_vergil.pdf", None, 30, "Arma virumque", 249),
    ("K7", "classics", "reference", r"teubner/conte_aeneis.pdf", None, 30, "arma uirumque", 48),
    ("K8", "classics", "reference", r"teubner/west_ilias1.pdf", None, 30, "μῆνιν", 62),
]

rows = []
for sid, branch, typ, pat, kw, win, target, override in SPECS:
    hits = sorted(glob.glob(os.path.join(BASE, pat), recursive=True))
    if kw:
        hits = [h for h in hits if kw in os.path.basename(h)] or hits
    if not hits:
        rows.append({"id": sid, "error": "not found", "pattern": pat})
        continue
    path = hits[0]
    size = os.path.getsize(path)
    sha = sha_sample(path, size)
    d = pymupdf.open(path)
    pages = d.page_count
    start = override if override is not None else max(5, int(pages * 0.2))
    if target and override is None:
        for i in range(min(pages, 400)):
            t = (d.load_page(i).get_text("text") or "").lower()
            if target.lower() in t:
                start = max(2, i - 2)
                break
    start = min(start, max(0, pages - win))
    d.close()
    gold = [start + 5, start + win // 2, start + win - 5]
    gold = [g for g in gold if start <= g < start + win]
    rows.append({
        "id": sid,
        "branch": branch,
        "type": typ,
        "path": path,
        "rel": os.path.relpath(path, BASE),
        "book_id": sha[:16],
        "sha256": sha,
        "size": size,
        "pages": pages,
        "window": {"start": start, "end": start + win - 1, "size": win},
        "gold_pages": gold,
    })

manifest = {
    "created": "2026-10-29",
    "roots": {"library": "D:/Guo-Code/PDF", "steadman": "D:/Guo-Code/PDF-new/Steadman",
              "loeb": "D:/Guo-Code/loeb", "teubner": "D:/Guo-Code/teubner"},
    "samples": rows,
}
with open(os.path.join(OUT, "sample-manifest.json"), "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, ensure_ascii=False, indent=1)

# combined catalog: library (from D0 hash manifest) + Steadman + Loeb + Teubner
catalog = []
lib_manifest = os.path.join(OUT, "hash-manifest.jsonl")
if os.path.exists(lib_manifest):
    with open(lib_manifest, encoding="utf-8") as fh:
        for line in fh:
            m = json.loads(line)
            m["root"] = "library"
            catalog.append(m)
for root_name, root in (("steadman", os.path.join(BASE, "PDF-new", "Steadman")),
                        ("loeb", os.path.join(BASE, "loeb")),
                        ("teubner", os.path.join(BASE, "teubner"))):
    for dirpath, _d, files in os.walk(root):
        for fn in files:
            if not fn.lower().endswith(".pdf"):
                continue
            p = os.path.join(dirpath, fn)
            s = os.path.getsize(p)
            h = sha_sample(p, s)
            catalog.append({"book_id": h[:16], "sha256": h, "size": s,
                            "rel": os.path.relpath(p, root), "root": root_name})
with open(os.path.join(OUT, "catalog.jsonl"), "w", encoding="utf-8") as fh:
    for m in catalog:
        fh.write(json.dumps(m, ensure_ascii=False) + "\n")

ok = [r for r in rows if "error" not in r]
print("samples", len(ok), "errors", len(rows) - len(ok))
for r in ok:
    print(f"{r['id']:3s} {r['branch']:12s} {r['type']:9s} p={r['pages']:4d} win={r['window']['start']}-{r['window']['end']} gold={r['gold_pages']} {os.path.basename(r['path'])[:55]}")
