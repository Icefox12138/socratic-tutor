import pymupdf,json
man={s["id"]:s for s in json.load(open(r"eval\p0\catalog\sample-manifest.json",encoding="utf-8"))["samples"]}
d=pymupdf.open(man["K5"]["path"])
with open(r"eval\p1\bakeoff\k5_greek_sample.txt","w",encoding="utf-8") as f:
 for p in [85,87,89]:
  t=d.load_page(p-1).get_text()
  f.write(f"--- p{p} ---\n{t[:800]}\n")
d.close()
