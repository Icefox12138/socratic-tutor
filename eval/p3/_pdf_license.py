import pymupdf
paths = [
 r"D:\Guo-Code\PDF\物理\理论力学\初识经典力学 陈童 东华理工大学.pdf",
 r"D:\Guo-Code\PDF\物理\量子力学\量子力学新讲 陈童 东华理工大学.pdf",
]
for p in paths:
    d = pymupdf.open(p)
    print("==", p.split("\\")[-1], "pages", d.page_count)
    for i in range(min(3, d.page_count)):
        txt = (d.load_page(i).get_text("text") or "").strip()
        print("  p%d: %s" % (i+1, txt[:300].replace("\n", " | ") if txt else "(no text layer)"))
    d.close()
