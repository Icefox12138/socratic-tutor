import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import toc  # noqa: E402

CHAPTERS = [
    {"level": 1, "title": "卷首", "page_start": 1, "page_end": 18, "volume": None},
    {"level": 1, "title": "卷1", "page_start": 20, "page_end": 70, "volume": 1},
    {"level": 1, "title": "卷2", "page_start": 71, "page_end": 120, "volume": 2},
]


class TestBindToVolume(unittest.TestCase):
    def test_inside(self):
        self.assertEqual(toc.bind_to_volume(40, CHAPTERS), 1)

    def test_title_page_just_before_the_header(self):
        # one leaf before its 卷 start still opens that 卷
        self.assertEqual(toc.bind_to_volume(19, CHAPTERS), 1)
        self.assertEqual(toc.bind_to_volume(70, CHAPTERS), 2)
        self.assertEqual(toc.bind_to_volume(71, CHAPTERS), 2)

    def test_title_page_several_leaves_early(self):
        # the header pass can miss the first leaves of a 卷
        self.assertEqual(toc.bind_to_volume(67, CHAPTERS), 2)

    def test_front_matter_stays_unbound(self):
        self.assertIsNone(toc.bind_to_volume(9, CHAPTERS))
        # Pages within the slack of a 卷 start bind to it: binding is lenient on
        # purpose (the header pass misses the first leaves). 目录 lines are
        # rejected by the title-shape filter in build_index, not here.
        self.assertEqual(toc.bind_to_volume(17, CHAPTERS), 1)


class TestPianSequence(unittest.TestCase):
    def test_keeps_increasing_numbers(self):
        cands = [(19, "武帝紀第一"), (60, "文帝紀第二")]
        self.assertEqual([c[0] for c in toc.pian_sequence(cands)], [19, 60])

    def test_drops_out_of_order(self):
        cands = [(30, "傳第九"), (40, "傳第七")]
        self.assertEqual([c[1] for c in toc.pian_sequence(cands)], ["傳第九"])

    def test_drops_list_page_runs(self):
        # 目录 pages spell out every 篇 on consecutive pages
        cands = [(5, "甲傳第一"), (6, "乙傳第二"), (7, "丙傳第三")]
        self.assertEqual([c[0] for c in toc.pian_sequence(cands)], [5])

    def test_ignores_lines_without_number(self):
        self.assertEqual(toc.pian_sequence([(9, "太史公自序")]), [])


if __name__ == "__main__":
    unittest.main()
