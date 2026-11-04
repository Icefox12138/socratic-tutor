import re, unicodedata, json, urllib.request
from pathlib import Path
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

def body_text(url):
    xml = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read().decode("utf-8")
    m = re.search(r"<body[^>]*>(.*?)</body>", xml, re.S)
    return re.sub(r"<[^>]+>", " ", m.group(1))

def sentences(s, lo=40, hi=320):
    parts = re.split(r"[.;·]+", s)
    return [p for p in (norm(x) for x in parts) if lo <= len(p) <= hi]

def evaluate(ref_text, hyp_text, label, cutoff=85):
    ref_s = sentences(ref_text)
    hyp = norm(hyp_text)
    step = 100
    windows = [hyp[i:i+400] for i in range(0, max(1, len(hyp)-400), step)]
    hits = []
    for s in ref_s:
        m = process.extractOne(s, windows, scorer=fuzz.partial_ratio, score_cutoff=cutoff)
        if not m:
            continue
        al = fuzz.partial_ratio_alignment(s, m[0], score_cutoff=cutoff)
        if not al:
            continue
        best = m[0][al.dest_start:al.dest_end]
        hits.append((s, best))
    chars = sum(len(a) for a, _ in hits)
    edits = sum(lev(a, b) for a, b in hits)
    cers = sorted(lev(a, b)/len(a) for a, b in hits)
    return {
        "label": label,
        "ref_sentences": len(ref_s), "matched": len(hits),
        "coverage": round(len(hits)/max(1, len(ref_s)), 3),
        "matched_chars": chars,
        "weighted_cer": round(edits/max(1, chars), 4),
        "median_cer": round(cers[len(cers)//2], 3) if cers else None,
        "p90_cer": round(cers[int(len(cers)*0.9)], 3) if cers else None,
    }

# Greek
greek_ref = body_text("https://raw.githubusercontent.com/PerseusDL/canonical-greekLit/master/data/tlg0059/tlg002/tlg0059.tlg002.perseus-grc2.xml")
greek_hyp = open(r"D:\Guo-Code\loeb\greek_plato.txt", encoding="utf-8", errors="replace").read()
g = evaluate(greek_ref, greek_hyp, "Plato Apology vs Perseus")

# Latin
latin_ref = body_text("https://raw.githubusercontent.com/PerseusDL/canonical-latinLit/master/data/phi0690/phi003/phi0690.phi003.perseus-lat2.xml")
latin_hyp = open(r"D:\Guo-Code\loeb\latin.txt", encoding="utf-8", errors="replace").read()
l = evaluate(latin_ref, latin_hyp, "Vergil Aeneid vs Perseus")

out = {"greek": g, "latin": l}
open(str(Path(__file__).with_suffix(".json")), "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False))
