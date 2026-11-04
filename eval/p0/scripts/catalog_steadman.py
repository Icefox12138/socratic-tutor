import csv, glob, json, os, re, unicodedata
import pymupdf

ROOT = r"D:\Guo-Code\PDF-new\Steadman"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "steadman-catalog.csv")

GREEK = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]")
LATIN_EXT = re.compile(r"[\u0100-\u024F]")
ASCII = re.compile(r"[A-Za-z]")
MACRON = re.compile(r"[\u0100-\u0105\u0112-\u0113\u012A-\u012B\u014C-\u014D\u016A-\u016B]")

def kind(name):
    n = name.lower()
    if "transsheet" in n or "trans-" in n or "translation" in n: return "translation_sheet"
    if "corelist" in n or "flashcard" in n or "core" in n: return "vocab_list"
    if "sample" in n or "preview" in n: return "sample"
    if "key" in n: return "answer_key"
    return "commentary"

rows = []
for f in sorted(glob.glob(os.path.join(ROOT, "*", "*.pdf"))):
    rel = os.path.relpath(f, ROOT)
    lang = rel.split(os.sep)[0]
    name = os.path.basename(f)
    rec = dict(lang=lang, name=name, slug=name.split("__")[0], kind=kind(name),
               mb=round(os.path.getsize(f)/2**20, 1), pages=None, greek=0, latin_ext=0,
               ascii=0, macron=False, fonts="", err="")
    try:
        d = pymupdf.open(f)
        rec["pages"] = d.page_count
        fonts = set()
        txt = []
        for p in range(min(6, d.page_count)):
            page = d.load_page(p)
            txt.append(page.get_text("text") or "")
            for fo in page.get_fonts():
                fonts.add(fo[3])
        t = "\n".join(txt)
        rec["greek"] = len(GREEK.findall(t))
        rec["latin_ext"] = len(LATIN_EXT.findall(t))
        rec["ascii"] = len(ASCII.findall(t))
        rec["macron"] = bool(MACRON.search(t))
        rec["fonts"] = ",".join(sorted(x.split("+")[-1] for x in fonts))[:80]
        d.close()
    except Exception as e:  # noqa: BLE001
        rec["err"] = type(e).__name__
    rows.append(rec)

with open(OUT, "w", newline="", encoding="utf-8-sig") as fh:
    wr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    wr.writeheader(); wr.writerows(rows)

by = {}
for r in rows:
    k = (r["lang"], r["kind"])
    a = by.setdefault(k, [0, 0, 0])
    a[0] += 1; a[1] += r["pages"] or 0; a[2] += r["mb"]
print("lang/kind | files | pages | MB")
for k in sorted(by):
    print(f"{k[0]:6s} {k[1]:18s} {by[k][0]:3d} {by[k][1]:6d} {by[k][2]:7.1f}")
print("\nTOTAL", len(rows), "files,", sum(r["pages"] or 0 for r in rows), "pages,",
      round(sum(r["mb"] for r in rows), 1), "MB")
print("text-layer check (ascii+greek+latin > 0 on first pages):",
      sum(1 for r in rows if (r["ascii"] + r["greek"] + r["latin_ext"]) > 0), "/", len(rows))
print("errors:", [r["name"] for r in rows if r["err"]])
print("\n-- largest 10 --")
for r in sorted(rows, key=lambda x: -(x["pages"] or 0))[:10]:
    print(f"{r['pages']:5d}p {r['mb']:6.1f}MB {r['lang']:5s} {r['kind']:16s} {r['name'][:60]}")
