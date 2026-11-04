"""Render a licence-free demo card for the README (our own data only)."""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(REPO, "docs", "assets", "public")
os.makedirs(OUT, exist_ok=True)

rows = json.load(open(os.path.join(REPO, "packages", "classics-index",
                                   "examples", "expected-toc.json"), encoding="utf-8"))["chapters"]

W, H = 980, 620
img = Image.new("RGB", (W, H), "#fbfaf7")
d = ImageDraw.Draw(img)
font = ImageFont.load_default()
try:
    font_big = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 22)
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 17)
    font_mono = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 16)
except Exception:
    font_big = font_mono = font

d.text((32, 26), "classics-index · 卷 / 篇 索引（示例数据）", font=font_big, fill="#1d1d1f")
d.line([(32, 66), (W - 32, 66)], fill="#ded5c4", width=1)
y = 86
for c in rows:
    indent = 34 if c["level"] == 2 else 0
    label = ("  " if c["level"] == 2 else "") + c["title"]
    d.text((32 + indent, y), label, font=font, fill="#1d1d1f" if c["level"] == 1 else "#6b6257")
    d.text((W - 260, y), "p.%d–%d" % (c["page_start"], c["page_end"]), font=font_mono, fill="#2f6f5e")
    y += 34
d.line([(32, H - 62), (W - 32, H - 62)], fill="#ded5c4", width=1)
d.text((32, H - 50), "生成自 packages/classics-index/examples（合成 12 页，无真实书页）· MIT",
       font=font, fill="#6b6257")
img.save(os.path.join(OUT, "classics-index-demo.png"))
print("wrote", os.path.join(OUT, "classics-index-demo.png"))
