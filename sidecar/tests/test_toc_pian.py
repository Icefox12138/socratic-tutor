import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import toc  # noqa: E402


BASE = [
    {"ord": 0, "level": 2, "title": "卷首", "page_start": 1, "page_end": 18, "volume": None},
    {"ord": 1, "level": 1, "title": "卷1", "page_start": 20, "page_end": 70, "volume": 1},
    {"ord": 2, "level": 1, "title": "卷2", "page_start": 71, "page_end": 120, "volume": 2},
    {"ord": 3, "level": 2, "title": "卷末", "page_start": 121, "page_end": 130, "volume": None},
]


class TestMergePian(unittest.TestCase):
    def test_title_page_moves_the_volume_start(self):
        rows = toc.merge_pian(BASE, {1: (19, "五帝本紀第一")}, total=130)
        vol1 = next(r for r in rows if r.get("volume") == 1 and r["level"] == 1)
        self.assertEqual(vol1["page_start"], 19)
        self.assertEqual(vol1["title"], "卷1 五帝本紀第一")

    def test_matter_rows_stay_level1(self):
        rows = toc.merge_pian(BASE, {1: (19, "五帝本紀第一")}, total=130)
        head = next(r for r in rows if r["title"] == "卷首")
        self.assertEqual(head["level"], 1)

    def test_pian_row_follows_its_volume(self):
        rows = toc.merge_pian(BASE, {1: (19, "五帝本紀第一")}, total=130)
        idx = next(i for i, r in enumerate(rows) if r.get("volume") == 1 and r["level"] == 1)
        self.assertEqual(rows[idx + 1]["level"], 2)
        self.assertEqual(rows[idx + 1]["title"], "五帝本紀第一")

    def test_level1_coverage_is_contiguous(self):
        rows = toc.merge_pian(BASE, {1: (19, "五帝本紀第一")}, total=130)
        level1 = [r for r in rows if r["level"] == 1]
        self.assertEqual(sum(r["pages"] for r in level1), 130)
        self.assertEqual(level1[0]["page_end"], 18)
        self.assertEqual(level1[-1]["page_end"], 130)

    def test_multiple_pian_in_one_volume(self):
        rows = toc.merge_pian(BASE, {1: [(19, "武帝紀第一"), (30, "文帝紀第二")]}, total=130)
        pian = [r for r in rows if r["level"] == 2 and r.get("volume") == 1]
        self.assertEqual([p["title"] for p in pian], ["武帝紀第一", "文帝紀第二"])
        self.assertEqual(pian[0]["page_start"], 19)
        self.assertEqual(pian[0]["page_end"], 29)
        self.assertEqual(pian[1]["page_end"], 70)   # last 篇 runs to the 卷 end

    def test_no_hits_changes_nothing(self):
        rows = toc.merge_pian(BASE, {}, total=130)
        self.assertEqual(len(rows), len(BASE))
        self.assertEqual([r["title"] for r in rows], [r["title"] for r in BASE])
