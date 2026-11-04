import unittest

from classics_index import hui


def rec(page, texts):
    return {"page": page, "texts": texts}


# Distinct 回 titles: two 回 with similar headers would be one segment.
TITLES = [
    "灵根育孕源流出心性修持", "悟彻菩提真妙理断魔归本", "四海千山皆拱伏九幽十类",
    "官封弼马心何足名注齐天", "乱蟠桃大圣偷丹反天宫", "观音赴会问原因小圣施威",
    "八卦炉中逃大圣五行山", "我佛造经传极乐观音奉旨", "陈光蕊赴任逢灾江流僧",
    "老龙王拙计犯天条魏征", "二将军宫门镇鬼唐太宗", "还受生唐王遵善果度孤魂",
]


def book(start, end, num, title, with_number=True):
    """Pages of one 回: the first leaf carries "第X回", the rest only the title."""
    out = []
    for p in range(start, end + 1):
        texts = [title]
        if with_number and p == start:
            texts.insert(0, "第%d回" % num)
        out.append(rec(p, texts))
    return out


class TestHui(unittest.TestCase):
    def test_segments_by_header(self):
        records = book(1, 5, 1, "灵根育孕源流出心性修持大道生")
        records += book(6, 10, 2, "悟彻菩提真妙理断魔归本合元神")
        rows = hui.build(records)[0]
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0]["page_start"], rows[0]["page_end"]), (1, 5))
        self.assertEqual(rows[1]["page_start"], 6)

    def test_short_run_is_merged(self):
        records = book(1, 5, 1, "甲乙丙丁戊己庚辛壬癸")
        records.append(rec(6, ["子丑寅卯辰巳午未申酉"]))   # one-leaf blip
        records += book(7, 11, 1, "甲乙丙丁戊己庚辛壬癸", with_number=False)
        rows = hui.build(records)[0]
        self.assertEqual(len(rows), 1)

    def test_appendix_does_not_consume_a_number(self):
        records = book(1, 5, 1, "灵根育孕源流出心性修持大道生")
        records += [rec(p, ["陈光蕊赴任逢灾江流僧复仇报本", "附", "录"]) for p in range(6, 11)]
        records += book(11, 15, 9, "袁守诚妙算无私曲老龙王拙计犯天条")
        rows = hui.build(records)[0]
        self.assertEqual(len(rows), 3)
        self.assertIn("附录", rows[1]["title_text"])
        self.assertEqual(rows[2]["num"], 3)

    def test_book_split_on_number_reset(self):
        records = []
        for i in range(1, 11):                      # a real novel runs well past 10
            records += book((i - 1) * 6 + 1, i * 6, i, TITLES[i - 1])
        records += book(61, 66, 1, "三国开篇宴桃园豪杰三结义")
        books = hui.build(records)
        self.assertEqual(len(books), 2)
        self.assertEqual(books[1][0]["page_start"], 61)


if __name__ == "__main__":
    unittest.main()
