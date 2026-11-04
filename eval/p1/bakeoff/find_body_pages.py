import pymupdf,json,re
man={s["id"]:s for s in json.load(open(r"eval\p0\catalog\sample-manifest.json",encoding="utf-8"))["samples"]}
G=re.compile("[\u0370-\u03ff\u1f00-\u1fff]")
for g in ("K5","K6"):
 d=pymupdf.open(man[g]["path"])
 out=[]
 for p in range(1,d.page_count+1):
  t=d.load_page(p-1).get_text()
  gr=len(G.findall(t)); letters=len(re.findall("[A-Za-z]",t)); words=len(re.findall(r"\b(the|and|of|to|in|that|with|for|is|was)\b",t,re.I))
  if gr>50 or (g=="K6" and letters>500 and words<3):
   out.append((p,gr,letters,words))
 d.close()
 print(g,"candidates",len(out))
 print(out[:40])
