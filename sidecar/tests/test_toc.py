import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import toc  # noqa: E402


class TestCn2Int(unittest.TestCase):
    def test_digits(self):
        self.assertEqual(toc.cn2int("12"), 12)

    def test_chinese(self):
        self.assertEqual(toc.cn2int("一"), 1)
        self.assertEqual(toc.cn2int("十"), 10)
        self.assertEqual(toc.cn2int("二十七"), 27)
        self.assertEqual(toc.cn2int("一百零五"), 105)


class TestVolumeOf(unittest.TestCase):
    def test_running_header(self):
        lines = [{"text": "莫不砥屬"}, {"text": "史記卷一"}]
        self.assertEqual(toc.volume_of(lines), 1)

    def test_no_header(self):
        self.assertIsNone(toc.volume_of([{"text": "正文"}]))


class TestBuild(unittest.TestCase):
    def test_ranges_are_contiguous(self):
        pages = {1: [{"text": "史記卷一"}], 2: [{"text": "史記卷一"}],
                 3: [{"text": "史記卷二"}], 4: [{"text": "史記卷二"}],
                 5: [{"text": "史記卷二"}]}
        ch = toc.build(pages)
        self.assertEqual([c["volume"] for c in ch], [1, 2])
        self.assertEqual((ch[0]["page_start"], ch[0]["page_end"]), (1, 2))
        self.assertEqual((ch[1]["page_start"], ch[1]["page_end"]), (3, 5))
        self.assertEqual(ch[1]["pages"], 3)

    def test_pages_without_header_are_skipped(self):
        pages = {1: [{"text": "封面"}], 2: [{"text": "史記卷一"}], 3: [{"text": "史記卷三"}]}
        ch = toc.build(pages)
        self.assertEqual([(c["volume"], c["page_start"]) for c in ch], [(1, 2), (3, 3)])

    def test_enrich_adds_pian_title(self):
        pages = {1: [{"text": "史記卷一 五帝本紀第一"}]}
        ch = toc.enrich(toc.build(pages), pages)
        self.assertIn("本紀第一", ch[0]["title"])


class TestStore(unittest.TestCase):
    def test_roundtrip(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        path = os.path.join(tmp, "state.db")
        chapters = [{"ord": 0, "level": 1, "title": "卷1", "page_start": 1,
                     "page_end": 10, "volume": 1, "pages": 10}]
        self.assertEqual(toc.save("library", "b.pdf", chapters, path=path), 1)
        got = toc.load("library", "b.pdf", path=path)
        self.assertEqual(got[0]["title"], "卷1")
        self.assertEqual(got[0]["page_end"], 10)
        self.assertEqual(toc.books(path=path)[0]["chapters"], 1)


if __name__ == "__main__":
    unittest.main()
