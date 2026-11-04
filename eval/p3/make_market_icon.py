"""Generate the DSH market icon (256x256 PNG, MIT)."""
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "market")
GREEN = (47, 111, 94, 255)
DEEP = (26, 66, 56, 255)
PAPER = (253, 252, 248, 255)
RULE = (201, 194, 180, 255)
ACCENT = (226, 138, 74, 255)

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# rounded tile
d.rounded_rectangle([0, 0, S - 1, S - 1], radius=56, fill=GREEN)
d.rounded_rectangle([0, 0, S - 1, S - 1], radius=56, outline=DEEP, width=4)

# page
d.rounded_rectangle([62, 40, 194, 216], radius=10, fill=PAPER)

# bookmark ribbon
d.polygon([(108, 40), (148, 40), (148, 92), (128, 76), (108, 92)], fill=ACCENT)

# text lines
for i, w in enumerate((86, 96, 74, 90)):
    y = 116 + i * 22
    d.rounded_rectangle([78, y, 78 + w, y + 9], radius=4, fill=RULE)

# citation pin: a dot with a page number tick
d.ellipse([150, 176, 182, 208], fill=GREEN, outline=PAPER, width=4)
d.rounded_rectangle([158, 190, 174, 195], radius=2, fill=PAPER)

os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, "icon.png")
img.save(path)
print("wrote", path, os.path.getsize(path), "bytes")
