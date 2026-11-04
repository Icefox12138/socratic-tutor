"""D0 preflight: paths, counts, hashes, disk, tools, sample books."""
import csv, glob, hashlib, json, os, shutil, sqlite3, subprocess, sys, time

BASE = r"D:\Guo-Code"
EVAL = os.path.join(BASE, "socratic-tutor", "eval", "p0")
for sub in ("catalog", "bench", "canary", "identity", "retrieval"):
    os.makedirs(os.path.join(EVAL, sub), exist_ok=True)

ROOTS = {
    "library": os.path.join(BASE, "PDF"),
    "steadman": os.path.join(BASE, "PDF-new", "Steadman"),
    "loeb": os.path.join(BASE, "loeb"),
    "teubner": os.path.join(BASE, "teubner"),
}
CHUNK = 4 * 1024 * 1024


def sha_sample(path, size):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read(CHUNK))
        if size > CHUNK * 2:
            fh.seek(-CHUNK, os.SEEK_END)
            h.update(fh.read(CHUNK))
    h.update(str(size).encode())
    return h.hexdigest()


def count_pdfs(root):
    out = []
    for dirpath, _d, files in os.walk(root):
        for fn in files:
            if fn.lower().endswith(".pdf"):
                p = os.path.join(dirpath, fn)
                try:
                    out.append((p, os.path.getsize(p)))
                except OSError:
                    pass
    return out


def tool_version(cmd):
    exe = shutil.which(cmd)
    if not exe:
        return None
    try:
        r = subprocess.run([exe] + (["--version"] if cmd != "uv" else ["--version"]),
                           capture_output=True, text=True, timeout=30)
        return (r.stdout or r.stderr).strip().splitlines()[0]
    except Exception as e:
        return f"ERR {e}"


def fts5_ok():
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        con.close()
        return True
    except Exception:
        return False


t0 = time.time()
report = {"roots": {}, "hashes": {}, "env": {}, "samples": {}, "disk": {}, "pages": {}}

for name, root in ROOTS.items():
    exists = os.path.isdir(root)
    files = count_pdfs(root) if exists else []
    total = sum(s for _, s in files)
    report["roots"][name] = {"path": root, "exists": exists, "pdfs": len(files),
                             "gb": round(total / 2**30, 2)}

# hash the main library
lib = count_pdfs(ROOTS["library"])
manifest = []
seen = {}
t1 = time.time()
for p, size in lib:
    try:
        h = sha_sample(p, size)
    except Exception as e:
        h = "ERR"
    rel = os.path.relpath(p, ROOTS["library"])
    manifest.append({"book_id": h[:16], "sha256": h, "size": size, "rel": rel})
    seen.setdefault(h, []).append(rel)

with open(os.path.join(EVAL, "catalog", "hash-manifest.jsonl"), "w", encoding="utf-8") as fh:
    for m in manifest:
        fh.write(json.dumps(m, ensure_ascii=False) + "\n")

dups = {k: v for k, v in seen.items() if len(v) > 1}
report["hashes"] = {"files": len(manifest), "elapsed_s": round(time.time() - t1, 1),
                    "unique": len(seen), "dup_groups": len(dups),
                    "dup_examples": list(dups.values())[:3]}

# disk
try:
    du = shutil.disk_usage(BASE)
    report["disk"] = {"total_gb": round(du.total / 2**30, 1), "free_gb": round(du.free / 2**30, 1),
                      "pass": du.free / 2**30 >= 300}
except Exception as e:
    report["disk"] = {"error": str(e)}

# env
try:
    import pymupdf
    pym = pymupdf.__version__
except Exception:
    pym = None
try:
    import rapidfuzz
    rf = rapidfuzz.__version__
except Exception:
    rf = None

report["env"] = {
    "python": sys.version.split()[0],
    "uv": tool_version("uv"),
    "dsh": tool_version("dsh"),
    "pymupdf": pym,
    "rapidfuzz": rf,
    "sqlite_fts5": fts5_ok(),
}

# sample books
PATTERNS = {
    "A1_princeton": r"PDF/数学/**/*Princeton calculus Reader*.pdf",
    "A2_lishangzhi": r"PDF/数学/**/*线性代数 _ 数学专业用*.pdf",
    "A3_cprimer": r"PDF/计算机/**/*Primer C++*.pdf",
    "A4_berkeley": r"PDF/物理/伯克利物理学教程/*.pdf",
    "B1_lenin2": r"PDF/马列主义/**/*列宁选集第二卷*.pdf",
    "B2_republic": r"PDF/西方文史哲/**/*理想国*.pdf",
    "B3_luxun01": r"PDF/中国文史哲/鲁迅全集/*01*.pdf",
    "B4_capital": r"PDF/马列主义/**/*资本论第一卷*.pdf",
    "C1_shiji": r"PDF/中国文史哲/二十四史*/**/01001*.pdf",
    "C2_shisanjing": r"PDF/中国文史哲/十三经注疏/01*.pdf",
    "C3_tongjian": r"PDF/中国文史哲/资治通鉴中华书局点校本/**/*.pdf",
    "C4_jinyong": r"PDF/中国文史哲/金庸*/**/*01*.pdf",
    "K1_apology": r"PDF-new/Steadman/greek/platos-apology__*.pdf",
    "K2_vergil": r"PDF-new/Steadman/latin/ap-vergil-usa__collegevergil*.pdf",
    "K3_herodotus": r"PDF-new/Steadman/greek/files-herodotus__*.pdf",
    "K4_livy": r"PDF-new/Steadman/latin/livy__*.pdf",
    "K5_loeb_plato": r"loeb/greek_L036_plato.pdf",
    "K6_loeb_vergil": r"loeb/latin_L063N_vergil.pdf",
    "K7_teubner_conte": r"teubner/conte_aeneis.pdf",
    "K8_teubner_west": r"teubner/west_ilias1.pdf",
}
for key, pat in PATTERNS.items():
    hits = sorted(glob.glob(os.path.join(BASE, pat), recursive=True))
    report["samples"][key] = {"found": len(hits), "first": os.path.basename(hits[0]) if hits else None}

# page count baseline (reuse prior full probe if present)
probe = os.path.join(os.environ.get("TEMP", ""), "pdf_probe2.csv")
pages = {"source": "prior probe", "files": None, "pages": None}
if os.path.exists(probe):
    n = p = 0
    with open(probe, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            n += 1
            p += int(row.get("pages") or 0)
    pages.update({"files": n, "pages": p})
else:
    pages["source"] = "missing"
report["pages"] = pages

# write markdown
now = time.strftime("%Y-%m-%d %H:%M:%S")
lines = [f"# D0 preflight 报告", "", f"- 时间：{now}", f"- 根目录：`{BASE}`", ""]
lines.append("## 1. 根目录与规模")
lines.append("")
lines.append("| 根 | 存在 | PDF 数 | GB |")
lines.append("|---|---:|---:|---:|")
for k, v in report["roots"].items():
    lines.append(f"| {k} | {'是' if v['exists'] else '否'} | {v['pdfs']} | {v['gb']} |")
lines.append("")
lines.append("## 2. 哈希抽样")
h = report["hashes"]
lines.append("")
lines.append(f"- 文件数：{h['files']}；唯一：{h['unique']}；重复组：{h['dup_groups']}；耗时：{h['elapsed_s']} s")
lines.append(f"- 清单：`eval/p0/catalog/hash-manifest.jsonl`")
if h["dup_examples"]:
    lines.append(f"- 重复示例：{h['dup_examples']}")
lines.append("")
lines.append("## 3. 磁盘与环境")
lines.append("")
d = report["disk"]
lines.append(f"- D: 可用 {d.get('free_gb')} GB（要求 ≥300 GB）：{'PASS' if d.get('pass') else 'FAIL'}")
e = report["env"]
lines.append(f"- Python {e['python']}；uv={e['uv']}；DSH={e['dsh']}")
lines.append(f"- PyMuPDF={e['pymupdf']}；rapidfuzz={e['rapidfuzz']}；SQLite FTS5={e['sqlite_fts5']}")
lines.append("")
lines.append("## 4. 20 本样本可用性")
lines.append("")
lines.append("| 样本 | 命中 | 首个文件 |")
lines.append("|---|---:|---|")
for k, v in report["samples"].items():
    lines.append(f"| {k} | {v['found']} | {v['first'] or '—'} |")
lines.append("")
lines.append("## 5. 页数基线")
lines.append("")
lines.append(f"- 来源：{pages['source']}；文件 {pages['files']}；总页数 {pages['pages']}")
lines.append("")
# verdict
fails = []
if not report["roots"]["library"]["exists"]:
    fails.append("馆藏根不存在")
if report["roots"]["library"]["pdfs"] != 801:
    fails.append(f"馆藏 PDF 数 {report['roots']['library']['pdfs']} != 801")
if not d.get("pass"):
    fails.append("D: 可用空间不足 300 GB")
if any(v["found"] == 0 for v in report["samples"].values()):
    fails.append("有样本未命中：" + ",".join(k for k, v in report["samples"].items() if v["found"] == 0))
lines.append("## 判定")
lines.append("")
lines.append("**PASS**" if not fails else "**FAIL**：" + "；".join(fails))
lines.append("")

with open(os.path.join(EVAL, "preflight.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
with open(os.path.join(EVAL, "catalog", "preflight.json"), "w", encoding="utf-8") as fh:
    json.dump(report, fh, ensure_ascii=False, indent=1)

print(json.dumps({"roots": report["roots"], "hashes": {k: v for k, v in h.items() if k != "dup_examples"},
                  "disk": d, "env": e, "fails": fails}, ensure_ascii=False, indent=1))
print("elapsed", round(time.time() - t0, 1))
