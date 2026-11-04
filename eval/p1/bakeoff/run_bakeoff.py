"""P1-3c: four-engine OCR bake-off (60 pages, 5 page types).

Engines: rapidocr (default), paddleocr, umi (HTTP), mineru (CLI), ocrflux (HF model).
Gold is optional: put gold/<group>/<page>.txt; otherwise CER is left blank.

Usage:
  python run_bakeoff.py --engines rapidocr --pages 12
  python run_bakeoff.py --engines rapidocr,paddleocr
  python run_bakeoff.py --engines umi --umi-url http://127.0.0.1:1224
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

import pymupdf

BASE = r"D:\Guo-Code"
OUT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(OUT, "pages")
RESULT = os.path.join(OUT, "out")
GOLD = os.path.join(OUT, "gold")
MANIFEST = os.path.join(BASE, "socratic-tutor", "eval", "p0", "catalog", "sample-manifest.json")

GROUPS = {
    "C1": {"label": "史记竖排", "manual": ["列序", "注文错分"]},
    "B2": {"label": "理想国横排", "manual": ["脚注分离", "结构 F1"]},
    "K5": {"label": "Loeb 希腊", "manual": ["变音符"]},
    "K6": {"label": "Loeb 拉丁", "manual": ["行对齐"]},
    "A2": {"label": "李尚志公式", "manual": ["公式 CDM", "表格 TEDS"]},
    "A1": {"label": "Princeton 文本层", "manual": ["表格", "bbox 覆盖"]},
    "B4": {"label": "资本论文本层", "manual": ["脚注", "表格"]},
}

GREEK = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
POLY = re.compile(r"[\u1f00-\u1fff]")
CJK = re.compile(r"[\u3400-\u9fff]")
LATIN = re.compile(r"[A-Za-z]")


def norm(s):
    return re.sub(r"[^\u3400-\u9fffA-Za-z\u0370-\u03ff\u1f00-\u1fff]", "", s or "")


def lev(a, b):
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def page_png(pdf, page, dpi=200):
    os.makedirs(CACHE, exist_ok=True)
    out = os.path.join(CACHE, f"{os.path.basename(pdf)[:20]}_{page}_{dpi}.png")
    if not os.path.exists(out):
        d = pymupdf.open(pdf)
        pix = d.load_page(page - 1).get_pixmap(dpi=dpi)
        pix.save(out)
        d.close()
    return out


# ---------------- engines ----------------
def run_rapidocr(img):
    from rapidocr_onnxruntime import RapidOCR
    global _rapid
    try:
        _rapid
    except NameError:
        _rapid = RapidOCR()
    res, _ = _rapid(img)
    return "\n".join(x[1] for x in (res or []))


def run_paddleocr(img):
    from paddleocr import PaddleOCR
    global _paddle
    try:
        _paddle
    except NameError:
        try:
            _paddle = PaddleOCR(use_doc_orientation_classify=False,
                                use_doc_unwarping=False,
                                use_textline_orientation=False,
                                lang="ch", enable_mkldnn=False,
                                text_detection_model_name="PP-OCRv5_mobile_det",
                                text_recognition_model_name="PP-OCRv5_mobile_rec")
        except TypeError:
            _paddle = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    if hasattr(_paddle, "predict"):
        res = _paddle.predict(img)
        lines = []
        for page in res or []:
            lines.extend(page.get("rec_texts", []) if hasattr(page, "get") else [])
        return "\n".join(lines)
    res = _paddle.ocr(img, cls=True)
    lines = []
    for page in res or []:
        for line in page or []:
            lines.append(line[1][0])
    return "\n".join(lines)


def run_umi(img, url):
    import requests
    with open(img, "rb") as fh:
        r = requests.post(url.rstrip("/") + "/api/ocr", files={"image": fh}, timeout=120)
    r.raise_for_status()
    data = r.json()
    return "\n".join(x.get("text", "") for x in data.get("data", []) if isinstance(x, dict))


MINERU = r"D:\Guo-Code\socratic-tutor\.venv-mineru\Scripts\mineru.exe"


def run_mineru(pdf, page, outdir):
    os.makedirs(outdir, exist_ok=True)
    d = pymupdf.open(pdf)
    single = os.path.join(outdir, f"p{page}.pdf")
    doc = pymupdf.open()
    doc.insert_pdf(d, from_page=page - 1, to_page=page - 1)
    doc.save(single)
    doc.close()
    d.close()
    out = os.path.join(outdir, f"p{page}.md")
    if os.path.exists(out):
        os.remove(out)
    subprocess.run([MINERU, "parse", single, "--tier", "flash", "-p", "1",
                    "-o", out, "--wait", "180"],
                   check=True, timeout=600,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.isfile(out):
        return open(out, encoding="utf-8").read()
    md = []
    for dp, _d, fs in os.walk(outdir):
        for f in fs:
            if f.endswith(".md"):
                md.append(open(os.path.join(dp, f), encoding="utf-8").read())
    return "\n".join(md)


def run_ocrflux(img, model):
    from transformers import pipeline
    global _flux
    try:
        _flux
    except NameError:
        _flux = pipeline("image-to-text", model=model)
    return _flux(img)[0]["generated_text"]


_ODL_CACHE = {}


def run_pymupdf(pdf, page):
    d = pymupdf.open(pdf)
    text = d.load_page(page - 1).get_text("text") or ""
    d.close()
    return text


def run_opendataloader(pdf, group):
    if group in _ODL_CACHE:
        return _ODL_CACHE[group]
    import opendataloader_pdf
    outdir = os.path.join(RESULT, "opendataloader", group)
    os.makedirs(outdir, exist_ok=True)
    opendataloader_pdf.convert(
        input_path=[pdf], output_dir=outdir, format="markdown",
        markdown_page_separator="<!--PAGE:%page-number%-->", quiet=True)
    md = ""
    for dp, _d, fs in os.walk(outdir):
        for f in fs:
            if f.endswith(".md"):
                md += open(os.path.join(dp, f), encoding="utf-8").read()
    parts = re.split(r"<!--PAGE:(\d+)-->", md)
    page_map = {}
    for i in range(1, len(parts) - 1, 2):
        page_map[int(parts[i])] = parts[i + 1]
    _ODL_CACHE[group] = page_map
    return page_map


# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engines", default="rapidocr")
    ap.add_argument("--groups", default="C1,B2,K5,K6,A2")
    ap.add_argument("--pages", type=int, default=12)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--umi-url", default="http://127.0.0.1:1224")
    ap.add_argument("--ocrflux-model", default="")
    ap.add_argument("--parser", default="none", choices=["none", "pymupdf", "opendataloader"])
    args = ap.parse_args()

    manifest = {s["id"]: s for s in json.load(open(MANIFEST, encoding="utf-8"))["samples"]}
    if args.parser != "none":
        engines = [args.parser]
    else:
        engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    groups = [g.strip() for g in args.groups.split(",") if g.strip()]
    os.makedirs(RESULT, exist_ok=True)

    rows = []
    for g in groups:
        s = manifest[g]
        start, end = s["window"]["start"], s["window"]["end"]
        step = max(1, (end - start) // args.pages)
        pages = list(range(start, end + 1, step))[: args.pages]
        for pno in pages:
            img = page_png(s["path"], pno, args.dpi) if args.parser == "none" else ""
            for eng in engines:
                t0 = time.perf_counter()
                status, text, err = "ok", "", ""
                try:
                    if args.parser != "none":
                        if eng == "pymupdf":
                            text = run_pymupdf(s["path"], pno)
                        elif eng == "opendataloader":
                            text = run_opendataloader(s["path"], g).get(pno, "")
                        else:
                            raise RuntimeError(f"unknown parser {eng}")
                    elif eng == "rapidocr":
                        text = run_rapidocr(img)
                    elif eng == "paddleocr":
                        text = run_paddleocr(img)
                    elif eng == "umi":
                        text = run_umi(img, args.umi_url)
                    elif eng == "mineru":
                        text = run_mineru(s["path"], pno, os.path.join(RESULT, "mineru", g))
                    elif eng == "ocrflux":
                        if not args.ocrflux_model:
                            raise RuntimeError("--ocrflux-model required")
                        text = run_ocrflux(img, args.ocrflux_model)
                    else:
                        raise RuntimeError(f"unknown engine {eng}")
                except Exception as e:
                    status, err = "skipped", str(e)[:160]
                ms = (time.perf_counter() - t0) * 1000
                d = os.path.join(RESULT, eng, g)
                os.makedirs(d, exist_ok=True)
                if text:
                    open(os.path.join(d, f"p{pno}.txt"), "w", encoding="utf-8").write(text)
                gold_path = os.path.join(GOLD, g, f"p{pno}.txt")
                cer = None
                poly_recall = None
                if os.path.exists(gold_path):
                    gold = open(gold_path, encoding="utf-8").read()
                    a, b = norm(gold), norm(text)
                    if a:
                        cer = round(lev(a, b) / len(a), 4)
                    gp = len(POLY.findall(gold))
                    if gp:
                        poly_recall = round(len(POLY.findall(text)) / gp, 3)
                rows.append({"group": g, "page": pno, "engine": eng, "status": status,
                             "ms": round(ms, 1), "chars": len(text),
                             "cjk": len(CJK.findall(text)), "greek": len(GREEK.findall(text)),
                             "latin": len(LATIN.findall(text)), "cer": cer,
                             "poly_recall": poly_recall, "error": err})

    json.dump(rows, open(os.path.join(OUT, "scorecard.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # markdown scorecard
    lines = ["# OCR 四引擎 60 页 bake-off 记分卡", "",
             "| 引擎 | 组 | 页数 | 平均字符 | 平均 ms | CER | 变音符召回 | 手动项 |",
             "|---|---|---:|---:|---:|---:|---:|---|"]
    for eng in engines:
        for g in groups:
            sub = [r for r in rows if r["engine"] == eng and r["group"] == g and r["status"] == "ok"]
            if not sub:
                lines.append(f"| {eng} | {g} | 0 | - | - | - | - | 未运行/跳过 |")
                continue
            cer = [r["cer"] for r in sub if r["cer"] is not None]
            poly = [r["poly_recall"] for r in sub if r["poly_recall"] is not None]
            lines.append(
                f"| {eng} | {g} | {len(sub)} | {round(sum(r['chars'] for r in sub)/len(sub))} | "
                f"{round(sum(r['ms'] for r in sub)/len(sub),1)} | "
                f"{round(sum(cer)/len(cer),4) if cer else '-'} | "
                f"{round(sum(poly)/len(poly),3) if poly else '-'} | "
                f"{'/'.join(GROUPS[g]['manual'])} |")
    lines += ["", "> CER/变音符召回仅在 `gold/<组>/<页>.txt` 存在时计算；竖排列序、注文错分、公式 CDM、表格 TEDS 需人工填写。", ""]
    open(os.path.join(OUT, "scorecard.md"), "w", encoding="utf-8").write("\n".join(lines))
    print(json.dumps({"rows": len(rows), "ok": sum(1 for r in rows if r["status"] == "ok"),
                      "skipped": sum(1 for r in rows if r["status"] != "ok")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
