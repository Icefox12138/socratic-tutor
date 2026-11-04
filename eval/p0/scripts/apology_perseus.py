import re, unicodedata, difflib, json, urllib.request
from pathlib import Path
import pymupdf

def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z\u0370-\u03ff]", "", s)

def lev(a, b):
    if len(a) < len(b): a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

xml = urllib.request.urlopen(urllib.request.Request(
    "https://raw.githubusercontent.com/PerseusDL/canonical-greekLit/master/data/tlg0059/tlg002/tlg0059.tlg002.perseus-grc2.xml",
    headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read().decode("utf-8")
body = xml.split("<body>")[1].split("</body>")[0]
body = re.sub(r"<[^>]+>", " ", body)
perseus = norm(body)

d = pymupdf.open(r"D:\Guo-Code\loeb\greek_L036_plato.pdf")
loeb_raw = "\n".join((d.load_page(i).get_text("text") or "") for i in range(84, 147))
d.close()
loeb = norm(loeb_raw)

sm = difflib.SequenceMatcher(None, loeb, perseus, autojunk=True)
blocks = [m for m in sm.get_matching_blocks() if m.size >= 100]
cers = []
chars = edits = 0
for m in blocks:
    a, b = loeb[m.a:m.a+m.size], perseus[m.b:m.b+m.size]
    e = lev(a, b)
    chars += m.size; edits += e
    cers.append(e / m.size)
cers.sort()
res = {
    "loeb_greek_chars": len(loeb), "perseus_greek_chars": len(perseus),
    "blocks": len(blocks), "matched_chars": chars,
    "coverage_of_loeb": round(chars / max(1, len(loeb)), 3),
    "weighted_cer": round(edits / max(1, chars), 4),
    "median_block_cer": round(cers[len(cers)//2], 3) if cers else None,
    "p90_block_cer": round(cers[int(len(cers)*0.9)], 3) if cers else None,
}
open(str(Path(__file__).with_suffix(".json")), "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
print(res)
