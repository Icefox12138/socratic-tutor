"""Generate the market icon for dsh-socratic-curriculum (256x256 PNG, MIT).

Same rounded-tile family as make_market_icon.py / make_persona_icon.py; the
motif is a small stack of pages with a bookmark, because this bundle is about
following a course one page at a time.
"""
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "market")
INDIGO = (105, 65, 198, 255)
DEEP = (64, 40, 122, 255)
PAPER = (253, 252, 248, 255)
ACCENT = (226, 138, 74, 255)

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# rounded tile
d.rounded_rectangle([0, 0, S - 1, S - 1], radius=56, fill=INDIGO)
d.rounded_rectangle([0, 0, S - 1, S - 1], radius=56, outline=DEEP, width=4)

# page stack: back pages offset up-left, front page on top
d.rounded_rectangle([66, 44, 174, 152], radius=12, fill=(150, 120, 220, 255))
d.rounded_rectangle([80, 58, 188, 166], radius=12, fill=(178, 150, 235, 255))
d.rounded_rectangle([94, 72, 202, 196], radius=14, fill=PAPER)

# text lines on the front page
for i, y in enumerate((100, 122, 144)):
    d.rounded_rectangle([112, y, 184 - i * 18, y + 7], radius=3,
                        fill=(105, 65, 198, 190) if i else ACCENT)

# bookmark ribbon hanging off the page
d.polygon([(160, 72), (186, 72), (186, 128), (173, 112), (160, 128)],
          fill=ACCENT)

os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, "curriculum-icon.png")
img.save(path)
print("wrote", path, os.path.getsize(path), "bytes")
