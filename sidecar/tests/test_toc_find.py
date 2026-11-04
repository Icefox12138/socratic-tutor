import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import toc  # noqa: E402

ROWS = [
    {"ord": 0, "level": 1, "title": "卷首", "page_start": 1, "page_end": 18, "volume": None},
    {"ord": 1, "level": 1, "title": "卷1 五帝本紀第一", "page_start": 19, "page_end": 66, "volume": 1},
    {"ord": 2, "level": 2, "title": "五帝本紀第一", "page_start": 19, "page_end": 66, "volume": 1},
    {"ord": 3, "level": 1, "title": "卷2 夏本紀第二", "page_start": 67, "page_end": 108, "volume": 2},
    {"ord": 4, "level": 2, "title": "夏本紀第二", "page_start": 67, "page_end": 108, "volume": 2},
]


class TestAt(unittest.TestCase):
    def test_innermost_chapter(self):
        row = toc.at(ROWS, 40)
        self.assertEqual(row["level"], 2)
        self.assertEqual(row["title"], "五帝本紀第一")

    def test_front_matter(self):
        self.assertEqual(toc.at(ROWS, 5)["title"], "卷首")

    def test_outside_any_chapter(self):
        self.assertIsNone(toc.at(ROWS, 999))


class TestFind(unittest.TestCase):
    def test_by_title_fragment(self):
        self.assertEqual(toc.find(ROWS, "夏本纪")["title"], "夏本紀第二")

    def test_by_juan_number(self):
        self.assertEqual(toc.find(ROWS, "卷2")["volume"], 2)

    def test_by_huiprinted_number(self):
        rows = [{"ord": 0, "level": 2, "title": "第一回 宴桃園豪傑三結義", "page_start": 5, "page_end": 20}]
        self.assertEqual(toc.find(rows, "第1回")["page_start"], 5)

    def test_unknown(self):
        self.assertIsNone(toc.find(ROWS, "不存在"))
