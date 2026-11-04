import os, json, time
from paddleocr import PaddleOCR
BASE=r"D:\Guo-Code"
man={s["id"]:s for s in json.load(open(r"D:\Guo-Code\socratic-tutor\eval\p0\catalog\sample-manifest.json",encoding="utf-8"))["samples"]}
s=man["K5"]
pages=list(range(s["window"]["start"], s["window"]["end"]+1, 2))[:12]
ocr=PaddleOCR(use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False,lang="ch",enable_mkldnn=False,text_detection_model_name="PP-OCRv5_mobile_det",text_recognition_model_name="PP-OCRv5_mobile_rec")
out=r"D:\Guo-Code\socratic-tutor\eval\p1\bakeoff\out\paddleocr\K5"
os.makedirs(out, exist_ok=True)
for p in pages:
    if os.path.exists(os.path.join(out,f"p{p}.txt")): continue
    img=os.path.join(r"D:\Guo-Code\socratic-tutor\eval\p1\bakeoff\pages", f"greek_L036_plato.pdf_{p}_200.png")
    t=time.time(); res=ocr.predict(img)
    lines=[]
    for r in res or []:
        lines.extend(r.get("rec_texts",[]) if hasattr(r,"get") else [])
    open(os.path.join(out,f"p{p}.txt"),"w",encoding="utf-8").write("\n".join(lines))
    print(p, round(time.time()-t,1), len(lines), flush=True)
