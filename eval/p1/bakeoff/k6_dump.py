import pymupdf,json
man={s["id"]:s for s in json.load(open(r"eval\p0\catalog\sample-manifest.json",encoding="utf-8"))["samples"]}
d=pymupdf.open(man["K6"]["path"])
with open(r"eval\p1\bakeoff\k6_text.txt","w",encoding="utf-8") as f:
 for p in range(251,274,2):
  t=d.load_page(p-1).get_text()
  f.write(f"--- p{p} ---\n{t[:500]}\n")
d.close()
