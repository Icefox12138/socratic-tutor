import json, re, urllib.request, collections

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DSH-research/1.0", "Connection": "close"}
ident = "Teubner-Edition-Collection"
d = json.load(urllib.request.urlopen(urllib.request.Request(
    f"https://archive.org/metadata/{ident}", headers=UA), timeout=60))
md = d["metadata"]
print("title:", md.get("title"))
print("creator:", md.get("creator"))
print("date:", md.get("date"))
print("collection:", md.get("collection"))
print("access-restricted:", md.get("access-restricted-item"))
print("licenseurl:", md.get("licenseurl"))
print("description:", (md.get("description") or "")[:300])
files = d["files"]
print("files:", len(files))
ext = collections.Counter()
size = collections.Counter()
for f in files:
    n = f["name"].lower()
    for e in (".pdf", ".txt", ".epub", ".djvu", ".xml", ".jp2", ".zip"):
        if n.endswith(e):
            ext[e] += 1
            size[e] += int(f.get("size", 0))
print("formats:", dict(ext))
for e in ext:
    print(f"  {e}: {ext[e]} files, {size[e]/2**30:.1f} GB")
# sample pdf names
pdfs = [f["name"] for f in files if f["name"].lower().endswith(".pdf")]
print("sample pdfs:")
for n in pdfs[:15]:
    print("  ", n[:90])
