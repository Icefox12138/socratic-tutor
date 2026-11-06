"""Generate the market icon for dsh-socratic-persona (256x256 PNG, MIT).

Same tile-and-page language as make_market_icon.py, but a dialogue bubble in the
indigo used by the console's anchor badge, so the two bundles read as one family
without being indistinguishable.
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

# dialogue bubble + tail
d.rounded_rectangle([52, 62, 204, 168], radius=26, fill=PAPER)
d.polygon([(96, 168), (96, 206), (136, 168)], fill=PAPER)

# three dots: question, pause, answer
for i, x in enumerate((88, 128, 168)):
    r = 12 if i != 1 else 9
    d.ellipse([x - r, 115 - r, x + r, 115 + r],
              fill=(INDIGO if i != 1 else ACCENT))

# small citation tick under the bubble, echoing the tools icon
d.rounded_rectangle([104, 186, 152, 194], radius=4, fill=PAPER)

os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, "persona-icon.png")
img.save(path)
print("wrote", path, os.path.getsize(path), "bytes")
