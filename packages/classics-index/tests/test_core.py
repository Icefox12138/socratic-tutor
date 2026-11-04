import unittest

from classics_index import core


ROWS = [
    {"ord": 0, "level": 1, "title": "卷首", "page_start": 1, "page_end": 18, "volume": None},
    {"ord": 1, "level": 1, "title": "卷1 五帝本紀第一", "page_start": 19, "page_end": 66, "volume": 1},
    {"ord": 2, "level": 2, "title": "五帝本紀第一", "page_start": 19, "page_end": 66, "volume": 1},
    {"ord": 3, "level": 1, "title": "卷2 夏本紀第二", "page_start": 67, "page_end": 108, "volume": 2},
    {"ord": 4, "level": 2, "title": "夏本紀第二", "page_start": 67, "page_end": 108, "volume": 2},
]


class TestCn2Int(unittest.TestCase):
    def test_values(self):
        self.assertEqual(core.cn2int("二十七"), 27)
        self.assertEqual(core.cn2int("一百零五"), 105)
        self.assertEqual(core.cn2int("12"), 12)


class TestVolumes(unittest.TestCase):
    def test_volume_of_running_header(self):
        self.assertEqual(core.volume_of([{"text": "正文"}, {"text": "史記卷二"}]), 2)

    def test_clean_drops_single_page_noise(self):
        vols = {10: 13, 11: None, 12: 28, 20: 1, 21: 1, 22: 1, 23: 1, 24: 1}
        clean = core.clean_volumes(vols, min_run=5)
        self.assertEqual(set(clean.values()), {1})

    def test_ranges_are_contiguous(self):
        vols = {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2, 9: 2, 10: 2}
        rows = core.build_from_volumes(core.clean_volumes(vols, min_run=5))
        self.assertEqual([r["volume"] for r in rows], [1, 2])
        self.assertEqual(rows[0]["page_end"], 5)


class TestBind(unittest.TestCase):
    def test_inside(self):
        self.assertEqual(core.bind_to_volume(40, ROWS), 1)

    def test_title_page_before_header(self):
        self.assertEqual(core.bind_to_volume(19, ROWS), 1)
        self.assertEqual(core.bind_to_volume(66, ROWS), 2)

    def test_far_front_matter(self):
        self.assertIsNone(core.bind_to_volume(5, ROWS))


class TestFind(unittest.TestCase):
    def test_fragment(self):
        self.assertEqual(core.find(ROWS, "夏本纪")["title"], "夏本紀第二")

    def test_juan(self):
        self.assertEqual(core.find(ROWS, "卷2")["volume"], 2)

    def test_missing(self):
        self.assertIsNone(core.find(ROWS, "不存在"))


class TestMergePian(unittest.TestCase):
    def test_start_moves_to_title_page(self):
        rows = core.merge_pian([r for r in ROWS if r["level"] == 1], {2: (67, "夏本紀第二")}, total=108)
        vol2 = [r for r in rows if r.get("volume") == 2 and r["level"] == 1][0]
        self.assertEqual(vol2["page_start"], 67)
        self.assertEqual(vol2["title"], "卷2 夏本紀第二")

    def test_multiple_pian_in_one_volume(self):
        level1 = [r for r in ROWS if r["level"] == 1]
        rows = core.merge_pian(level1, {1: [(19, "五帝本紀第一"), (30, "夏本紀第二")]}, total=108)
        pian = [r for r in rows if r["level"] == 2 and r.get("volume") == 1]
        self.assertEqual([p["page_start"] for p in pian], [19, 30])
        self.assertEqual(pian[0]["page_end"], 29)


if __name__ == "__main__":
    unittest.main()
