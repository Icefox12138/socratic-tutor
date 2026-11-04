"""Render synthetic "book page" samples for README / market screenshots.

All text is authored here (plus one public-domain Greek one-liner); no scanned
book, no third-party page. Five page types:

  formula.png        公式页（Cambria + 手绘分式/矩阵）
  zh-horizontal.png  横排中文 + 英文术语表
  zh-vertical.png    竖排繁体（右起、双行小注）
  latin.png          拉丁文（Times，Loeb 式行号）
  greek.png          希腊文（Palatino，含变音符、变格表）

  python eval/p3/make_sample_pages.py
"""
import os
import re

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(REPO, "docs", "assets", "public", "samples")

FONTS = "C:/Windows/Fonts/"
W, H = 1000, 1400
INK = "#1b1b1d"
MUTED = "#6f6a62"
RULE = "#c9c2b4"
PAPER = "#fdfcf8"

WORD = re.compile(r"[A-Za-z\u0370-\u03ff\u1f00-\u1fff\u00c0-\u024f]+")


def load(name, size):
    return ImageFont.truetype(FONTS + name, size)


def page(head_left="", head_right=""):
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.rectangle([28, 28, W - 28, H - 28], outline=RULE, width=1)
    if head_left or head_right:
        f = load("msyh.ttc", 16)
        d.text((56, 46), head_left, font=f, fill=MUTED)
        w = d.textlength(head_right, font=f)
        d.text((W - 56 - w, 46), head_right, font=f, fill=MUTED)
        d.line([(56, 74), (W - 56, 74)], fill=RULE, width=1)
    return img, d


def footer(d, text):
    f = load("msyh.ttc", 14)
    d.text((56, H - 58), text, font=f, fill=MUTED)


def wrap_mixed(d, text, font, width):
    """CJK breaks anywhere; Latin/Greek runs stay whole (no split words)."""
    tokens = []
    i = 0
    while i < len(text):
        m = WORD.match(text, i)
        if m:
            tokens.append(m.group(0))
            i = m.end()
        elif text[i] == "\n":
            tokens.append("\n")
            i += 1
        else:
            tokens.append(text[i])
            i += 1
    lines, cur = [], ""
    for tok in tokens:
        if tok == "\n":
            lines.append(cur)
            cur = ""
            continue
        trial = cur + tok
        if d.textlength(trial, font=font) > width and cur:
            lines.append(cur)
            cur = tok
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def block(d, lines, font, x, y, leading, fill=INK):
    for line in lines:
        d.text((x, y), line, font=font, fill=fill)
        y += leading
    return y


# ---------------------------------------------------------------- math layout

def frac_width(d, num, den, size):
    f = load("cambria.ttc", int(size * 0.72))
    return max(d.textlength(num, font=f), d.textlength(den, font=f)) + 8


def draw_frac(d, x, baseline, num, den, size, fill=INK):
    f = load("cambria.ttc", int(size * 0.72))
    w = frac_width(d, num, den, size)
    d.text((x + (w - d.textlength(num, font=f)) / 2, baseline - size * 0.78), num, font=f, fill=fill)
    d.line([(x + 2, baseline), (x + w - 2, baseline)], fill=fill, width=2)
    d.text((x + (w - d.textlength(den, font=f)) / 2, baseline + size * 0.18), den, font=f, fill=fill)
    return w


def part_width(d, p, size):
    f = load("cambria.ttc", size)
    if p[0] == "t":
        return d.textlength(p[1], font=f)
    if p[0] in ("sup", "sub"):
        return d.textlength(p[1], font=load("cambria.ttc", int(size * 0.66)))
    if p[0] == "paren":
        return d.textlength("(", font=load("cambria.ttc", int(size * 1.45)))
    return frac_width(d, p[1], p[2], size)


def line_width(d, parts, size):
    return sum(part_width(d, p, size) for p in parts)


def draw_line(d, parts, cx, baseline, size, fill=INK):
    x = cx - line_width(d, parts, size) / 2
    for p in parts:
        if p[0] == "t":
            f = load("cambria.ttc", size)
            d.text((x, baseline), p[1], font=f, fill=fill)
        elif p[0] == "sup":
            f = load("cambria.ttc", int(size * 0.66))
            d.text((x, baseline - size * 0.42), p[1], font=f, fill=fill)
        elif p[0] == "sub":
            f = load("cambria.ttc", int(size * 0.66))
            d.text((x, baseline + size * 0.30), p[1], font=f, fill=fill)
        elif p[0] == "paren":
            f = load("cambria.ttc", int(size * 1.45))
            d.text((x, baseline - size * 0.34), p[1], font=f, fill=fill)
        else:
            draw_frac(d, x, baseline, p[1], p[2], size, fill)
        x += part_width(d, p, size)


def draw_matrix(d, x, baseline, rows, size, fill=INK):
    f = load("cambria.ttc", size)
    col_w = max(d.textlength(c, font=f) for row in rows for c in row) + 26
    h = size * 1.3 * len(rows)
    top = baseline - size * 0.95
    for dx in (0, 8):
        d.line([(x + dx, top), (x + dx, top + h)], fill=fill, width=2)
    d.line([(x, top), (x + 8, top)], fill=fill, width=2)
    d.line([(x, top + h), (x + 8, top + h)], fill=fill, width=2)
    right = x + 8 + col_w * len(rows[0])
    for dx in (0, -8):
        d.line([(right + dx, top), (right + dx, top + h)], fill=fill, width=2)
    d.line([(right, top), (right - 8, top)], fill=fill, width=2)
    d.line([(right, top + h), (right - 8, top + h)], fill=fill, width=2)
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            d.text((x + 16 + c * col_w, top + size * 1.3 * r + 6), cell, font=f, fill=fill)
    return right - x


# ---------------------------------------------------------------------- pages

def formula_page():
    img, d = page("第三章　分析力学", "53")
    d.text((56, 96), "3.1　拉格朗日方程", font=load("msyh.ttc", 30), fill=INK)
    body = load("msyh.ttc", 20)
    y = block(d, wrap_mixed(d, "对一个由广义坐标刻画的保守系统，作用量取驻值即给出欧拉–拉格朗日方程。"
                               "这一写法不依赖具体的坐标选择，因此比牛顿方程更适合处理约束问题。",
                            body, W - 112), body, 56, 146, 34)

    y += 44
    draw_line(d, [("t", "L(q, q̇, t) = T − V")], W / 2, y, 40)
    y += 92
    draw_line(d, [("f", "d", "dt"), ("paren", "("), ("f", "∂L", "∂q̇"), ("paren", ")"),
                  ("t", " − "), ("f", "∂L", "∂q"), ("t", " = 0")], W / 2, y, 34)
    y += 96
    draw_line(d, [("t", "Z = ∫ e"), ("sup", "−x²"), ("t", " dx = √π ⁄ 2")], W / 2, y, 36)
    y += 74
    mx = W / 2 - 210
    d.text((mx, y - 12), "M =", font=load("cambria.ttc", 32), fill=INK)
    draw_matrix(d, mx + 66, y, [["a", "b"], ["c", "d"]], 24)
    d.text((mx + 226, y - 4), "det M = ad − bc ≠ 0", font=load("cambria.ttc", 26), fill=INK)

    y += 74
    d.line([(56, y), (W - 56, y)], fill=RULE, width=1)
    y += 20
    y = block(d, wrap_mixed(d, "例 3.1　设质点沿光滑曲线滑动，取弧长为广义坐标。写出拉格朗日量，"
                               "并由此导出运动方程。", body, W - 112), body, 56, y, 34)
    y += 4
    y = block(d, wrap_mixed(d, "解：以弧长 s 为坐标，动能只含 s 的一阶导数，势能由高度给出；"
                               "代入上式即得单摆型的方程。当振幅很小时，sin s ≈ s，方程化为简谐形式，"
                               "周期只与摆长有关，与振幅无关——这正是伽利略观察到的等时性。",
                            body, W - 112), body, 56, y, 34)
    y += 40
    draw_line(d, [("t", "s̈ + ω² sin s = 0,    ω² = g ⁄ l")], W / 2, y, 30)
    y += 56
    small = load("msyh.ttc", 17)
    y = block(d, wrap_mixed(d, "小结：拉格朗日量把约束吸收进坐标选择，方程的形式因此与坐标系无关；"
                               "能量守恒可由时间平移对称性导出，而不是额外假设。",
                            small, W - 112), small, 56, y, 30)
    y += 18
    d.line([(56, y), (W - 56, y)], fill=RULE, width=1)
    y += 16
    d.text((56, y), "符号表", font=load("msyh.ttc", 17), fill=MUTED)
    y += 30
    sym = [("L", "拉格朗日量"), ("T", "动能"), ("V", "势能"),
           ("q", "广义坐标"), ("q̇", "广义速度"), ("s", "弧长")]
    for i, (a, b) in enumerate(sym):
        col = i % 3
        row = i // 3
        x = 56 + col * 300
        yy = y + row * 34
        d.text((x, yy), a, font=load("cambria.ttc", 22), fill=INK)
        d.text((x + 40, yy + 4), b, font=load("msyh.ttc", 18), fill=INK)
    y += 34 * 2 + 16
    d.line([(56, y), (220, y)], fill=RULE, width=1)
    d.text((56, y + 8), "注：本页为排版样本，公式取教科书通用形式，文字为自制。",
           font=load("msyh.ttc", 15), fill=MUTED)
    footer(d, "合成样本 · 公式页 · 无版权书页 · MIT")
    img.save(os.path.join(OUT, "formula.png"))


def zh_horizontal_page():
    img, d = page("第二章　函数与极限", "17")
    d.text((56, 96), "2.1　极限的直观含义", font=load("msyh.ttc", 30), fill=INK)
    body = load("msyh.ttc", 21)
    text = ("当自变量无限接近某一点时，函数值若稳定地靠近同一个数，我们就说这个函数在该点有极限。"
            "这里的“靠近”不是一步一步走到，而是任意接近：只要距离足够小，结果就能落进预先给定的范围。"
            "正因如此，极限刻画的是趋势，而不是某一点的取值。\n"
            "把这句话说严谨，需要把“足够小”和“范围”都换成可以计算的量。十九世纪的数学家正是这样做的："
            "先给定一个正数，再要求存在另一个正数与之对应。这样定义出来的极限，不再依赖图形直觉，"
            "却仍与直觉一致——这是分析学得以严格化的起点。\n"
            "初学者常把极限值与函数值混为一谈。二者可以相等，也可以不等；可以都不存在，"
            "也可以一个存在另一个不存在。判断时先问：函数在该点附近有没有定义？再看取值的走向。"
            "若两侧走向不同，则双侧极限不存在，即便单侧极限各自都存在。")
    y = block(d, wrap_mixed(d, text, body, W - 112), body, 56, 150, 35)

    y += 24
    d.line([(56, y), (W - 56, y)], fill=RULE, width=1)
    y += 18
    d.text((56, y), "术语（Glossary）", font=load("msyh.ttc", 17), fill=MUTED)
    y += 30
    en = load("times.ttf", 19)
    terms = [("limit", "极限：趋近过程的终点值"),
             ("continuity", "连续：极限值恰好等于该点函数值"),
             ("epsilon–delta", "ε–δ 语言：把“任意接近”写成两个正数的关系"),
             ("divergence", "发散：不存在有限的趋近目标"),
             ("one-sided", "单侧极限：只从一侧趋近时的取值")]
    for term, gloss in terms:
        d.text((56, y), term, font=en, fill=INK)
        d.text((238, y), gloss, font=load("msyh.ttc", 19), fill=INK)
        y += 34

    y += 20
    d.text((56, y), "练习", font=load("msyh.ttc", 17), fill=MUTED)
    y += 30
    for i, q in enumerate(["用自己的话说明“任意接近”与“恰好等于”的区别。",
                           "举一个函数值等于极限值、却不连续的例子。",
                           "若把 ε 换成 2ε，定义是否改变？为什么？",
                           "写出 f(x)=|x|/x 在 x→0 时两侧的单侧极限。"], 1):
        y = block(d, wrap_mixed(d, "%d. %s" % (i, q), load("msyh.ttc", 19), W - 112),
                  load("msyh.ttc", 19), 56, y, 32)
        y += 6
    footer(d, "合成样本 · 横排中文/英文 · 无版权书页 · MIT")
    img.save(os.path.join(OUT, "zh-horizontal.png"))


def zh_vertical_page():
    img, d = page()
    text = ("學而時習之不亦說乎有朋自遠方來不亦樂乎人不知而不慍不亦君子乎"
            "吾日三省吾身為人謀而不忠乎與朋友交而不信乎傳不習乎"
            "溫故而知新可以為師矣學而不思則罔思而不學則殆"
            "知之為知之不知為不知是知也"
            "君子食無求飽居無求安敏於事而慎於言就有道而正焉"
            "不患人之不己知患不知人也"
            "禮之用和為貴先王之道斯為美小大由之"
            "信近於義言可復也恭近於禮遠恥辱也"
            "德不孤必有鄰君子喻於義小人喻於利"
            "見賢思齊焉見不賢而內自省也"
            "君子欲訥於言而敏於行"
            "歲寒然後知松柏之後凋也"
            "己所不欲勿施於人")
    f = load("msjh.ttc", 26)
    note_f = load("msjh.ttc", 13)
    cell = 30
    top = 92
    bottom = H - 104
    col_chars = int((bottom - top) / cell)
    x = W - 92
    for i, ch in enumerate("論學篇"):
        d.text((x + 6, top + i * (cell + 8)), ch, font=load("msjh.ttc", 27), fill=INK)
    x -= cell * 2.8

    i = 0
    col = 0
    while i < len(text) and x > 240:
        if col >= 2 and col % 3 == 2:          # 每三列插一列双行小注
            n1 = "注此為合成語句非真實古籍頁面"
            n2 = "排版樣本僅供截圖使用"
            for k, ch in enumerate(n1[: col_chars]):
                d.text((x + 2, top + k * 21), ch, font=note_f, fill=MUTED)
            for k, ch in enumerate(n2[: col_chars]):
                d.text((x + 24, top + k * 21), ch, font=note_f, fill=MUTED)
        else:
            chunk = text[i:i + col_chars]
            y = top
            for ch in chunk:
                d.text((x, y), ch, font=f, fill=INK)
                y += cell
            i += col_chars
        x -= cell * 2.0
        col += 1
    footer(d, "合成样本 · 竖排繁体（右起 + 双行小注）· 非真实古籍 · MIT")
    img.save(os.path.join(OUT, "zh-vertical.png"))


def latin_page():
    img, d = page("LIBER PRIMUS", "12")
    body = load("times.ttf", 21)
    text = ("Ars longa, vita brevis. Omnis doctrina a quaestione incipit: quid sit, quomodo fiat, "
            "cur ita sit. Qui nihil dubitat, nihil discit; qui omnia dubitat, nihil efficit. "
            "Itaque discipulus non prius respondere debet quam intellegit, magister vero non prius "
            "solvere quam quaesivit.\n"
            "Natura enim quaerendo se aperit, non praecipiendo. Saepe unum exemplum plus docet quam "
            "decem regulae, si modo exemplum totum perspicitur. Memoria rerum gestarum fallax est, "
            "memoria rationis firma: illam fortuna mutat, hanc disciplina servat. Quare non satis est "
            "audire aut legere, nisi et ratio reddatur.\n"
            "Ubi ratio deficit, ibi fides supplet; ubi autem fides fidem petit, ibi quaestio redit. "
            "Hoc igitur ordine procedendum est: primum dubitare, deinde quaerere, tum probare, "
            "postremo docere. Qui hunc ordinem servat, non facile decipitur; qui eum neglegit, "
            "multa discit et pauca intellegit.\n"
            "Sit ergo nobis propositum non multa scire, sed ea quae scimus firmiter tenere et aliis "
            "explicare posse. Nam doctrina quae non intellegitur oneri est, non ornamento.\n"
            "Saepe qui celerrime legit, tardissime intellegit; qui autem lente legit, etiam "
            "memoria tenet. Tempus igitur non perditur, cum in re una moramur, sed tunc maxime "
            "lucramur. Nec pudor est nescire quod nescias, sed pudor est simulare te scire. "
            "Omnis enim error ex eo nascitur, quod pro certo habemus quod incertum est.\n"
            "Sit tibi liber non dominus, sed comes: adsit cum quaeris, cedat cum cogitas. "
            "Quod si unam tantum sententiam ex toto libro perceperis et in vita servaveris, "
            "plus profecisti quam qui mille paginas percurrit et nihil retinuit.")
    y = 118
    lines = wrap_mixed(d, text, body, W - 200)
    for i, line in enumerate(lines):
        d.text((104, y), line, font=body, fill=INK)
        if i % 5 == 0:
            d.text((56, y + 3), str(i + 1), font=load("times.ttf", 14), fill=MUTED)
        y += 35

    y += 20
    d.line([(56, y), (W - 56, y)], fill=RULE, width=1)
    y += 16
    small = load("times.ttf", 17)
    d.text((56, y), "Nota: haec pagina speciminis causa composita est.", font=small, fill=MUTED)
    footer(d, "合成样本 · 拉丁文 · 仅一句为公版格言 · MIT")
    img.save(os.path.join(OUT, "latin.png"))


def greek_page():
    img, d = page("ΚΕΦΑΛΑΙΟΝ Α", "3")
    body = load("pala.ttf", 24)
    head = load("pala.ttf", 28)
    d.text((76, 100), "Τὸ ζῷον πολιτικόν", font=head, fill=INK)

    lines = [
        "ὁ ἄνθρωπος ζῷον πολιτικόν ἐστιν.",
        "ἡ μὲν φύσις οὐδὲν μάτην ποιεῖ,",
        "λόγος δὲ ψυχῆς ἐστιν ὁ ἑαυτὸν",
        "αὐξάνων λόγος.",
    ]
    y = 156
    for line in lines:
        d.text((76, y), line, font=body, fill=INK)
        y += 42

    y += 6
    d.line([(76, y), (W - 76, y)], fill=RULE, width=1)
    y += 18
    d.text((76, y), "Κλίσις τοῦ λόγος", font=load("pala.ttf", 22), fill=INK)
    d.text((360, y + 3), "（名词变格）", font=load("msyh.ttc", 17), fill=MUTED)
    y += 36
    rows = [("ὀνομαστική", "λόγος", "λόγοι"),
            ("γενική", "λόγου", "λόγων"),
            ("δοτική", "λόγῳ", "λόγοις"),
            ("αἰτιατική", "λόγον", "λόγους"),
            ("κλητική", "λόγε", "λόγοι")]
    colx = (76, 300, 520)
    hdr = load("pala.ttf", 18)
    d.text((colx[1], y), "ἑνικός", font=hdr, fill=MUTED)
    d.text((colx[2], y), "πληθυντικός", font=hdr, fill=MUTED)
    y += 28
    for name, sg, pl in rows:
        d.text((colx[0], y), name, font=load("pala.ttf", 20), fill=INK)
        d.text((colx[1], y), sg, font=load("pala.ttf", 22), fill=INK)
        d.text((colx[2], y), pl, font=load("pala.ttf", 22), fill=INK)
        y += 36

    y += 14
    d.line([(76, y), (W - 76, y)], fill=RULE, width=1)
    y += 18
    d.text((76, y), "Ἀσκήσεις", font=load("pala.ttf", 20), fill=MUTED)
    y += 32
    drills = ["1. λέγε· τί ἐστι ζῷον πολιτικόν;",
              "2. γράφε· ἡ ψυχὴ λόγον ἔχει.",
              "3. κλῖνε· ὁ λόγος, τοῦ λόγου, τῷ λόγῳ.",
              "4. μετάφραζε· φύσει πολιτικὸν ὁ ἄνθρωπος."]
    for line in drills:
        d.text((92, y), line, font=load("pala.ttf", 21), fill=INK)
        y += 36

    y += 12
    d.line([(76, y), (W - 76, y)], fill=RULE, width=1)
    y += 18
    d.text((76, y), "Ἀνάγνωσις", font=load("pala.ttf", 20), fill=MUTED)
    y += 32
    passage = ["ἡ δὲ ψυχὴ τὰ μὲν αἰσθάνεται, τὰ δὲ νοεῖ·",
               "καὶ ὅσα μὲν νοεῖ, ἀεὶ ταὐτά ἐστιν,",
               "ὅσα δὲ αἰσθάνεται, ἄλλοτε ἄλλως ἔχει."]
    for line in passage:
        d.text((92, y), line, font=load("pala.ttf", 21), fill=INK)
        y += 34

    y += 12
    gloss = load("msyh.ttc", 17)
    y = block(d, wrap_mixed(d, "释读练习：先用现代汉语复述第一句，再说明变音符号（重音、送气、长音）"
                               "各自承担什么信息；最后把变格与英语的格残余作比较。", gloss, W - 152),
              gloss, 76, y, 30)
    d.text((76, y + 6), "（首句为亚里士多德公版引文，其余为本样本自撰。）", font=gloss, fill=MUTED)
    footer(d, "合成样本 · 希腊文（含变音符）· 无版权书页 · MIT")
    img.save(os.path.join(OUT, "greek.png"))


def main():
    os.makedirs(OUT, exist_ok=True)
    formula_page()
    zh_horizontal_page()
    zh_vertical_page()
    latin_page()
    greek_page()
    for name in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, name)
        print("wrote %-22s %6.1f KB" % (name, os.path.getsize(p) / 1024))


if __name__ == "__main__":
    main()
