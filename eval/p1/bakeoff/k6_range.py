import pymupdf,json,re
man={s["id"]:s for s in json.load(open(r"eval\p0\catalog\sample-manifest.json",encoding="utf-8"))["samples"]}
d=pymupdf.open(man["K6"]["path"])
for p in range(245,286):
 t=d.load_page(p-1).get_text()
 words=len(re.findall(r"\b(the|and|of|to|in|that|with|for|is|was)\b",t,re.I))
 print(p,len(t),words,repr(t[:60].replace("\n"," ")))
d.close()
