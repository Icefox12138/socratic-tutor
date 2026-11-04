import re, unicodedata, json
from pathlib import Path
import pymupdf
from rapidfuzz import fuzz, process

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

lat = open(Path(__file__).resolve().parent.parent / "gold" / "aeneid.xml", encoding="utf-8").read()
start = lat.find('<div n="1" type="textpart" subtype="book">')
end = lat.find('<div n="2" type="textpart" subtype="book">', start)
book1 = lat[start:end]
lines = [(int(n), re.sub(r"<[^>]+>", " ", t)) for n, t in re.findall(r'<l n="(\d+)"[^>]*>(.*?)</l>', book1, re.S)]

d = pymupdf.open(r"D:\Guo-Code\teubner\conte_aeneis.pdf")
conte = norm("".join((d.load_page(i).get_text("text") or "") for i in range(d.page_count)))
d.close()
windows = [conte[i:i+240] for i in range(0, max(1, len(conte)-240), 60)]

hits = []
for n, t in lines:
    s = norm(t)
    if len(s) < 8: continue
    m = process.extractOne(s, windows, scorer=fuzz.partial_ratio, score_cutoff=80)
    if not m: continue
    al = fuzz.partial_ratio_alignment(s, m[0], score_cutoff=80)
    if al: hits.append((n, s, m[0][al.dest_start:al.dest_end]))

chars = sum(len(s) for _, s, _ in hits); edits = sum(lev(s, b) for _, s, b in hits)
cers = sorted(lev(s, b)/len(s) for _, s, b in hits)
res = {"lines": len(lines), "matched": len(hits), "coverage": round(len(hits)/len(lines),3),
       "weighted_cer": round(edits/max(1,chars),4), "median": round(cers[len(cers)//2],3),
       "p90": round(cers[int(len(cers)*0.9)],3)}
json.dump(res, open("conte_cer.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
print(res)
