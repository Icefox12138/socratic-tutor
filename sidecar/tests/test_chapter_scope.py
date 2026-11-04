import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import citations, config, search, toc  # noqa: E402

ROWS = [
    {"ord": 0, "level": 1, "title": "卷首", "page_start": 1, "page_end": 18, "volume": None},
    {"ord": 1, "level": 1, "title": "卷1 五帝本紀第一", "page_start": 19, "page_end": 66, "volume": 1},
    {"ord": 2, "level": 2, "title": "五帝本紀第一", "page_start": 19, "page_end": 66, "volume": 1},
    {"ord": 3, "level": 1, "title": "卷2 夏本紀第二", "page_start": 67, "page_end": 108, "volume": 2},
    {"ord": 4, "level": 2, "title": "夏本紀第二", "page_start": 67, "page_end": 108, "volume": 2},
]


class TestChapterRange(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "state.db")
        self.old = config.STATE_DB
        config.STATE_DB = self.db
        toc.save("library", "book.pdf", ROWS, path=self.db)

    def tearDown(self):
        config.STATE_DB = self.old

    def test_window_for_a_chapter(self):
        rng = search._range("book.pdf", "卷2")
        self.assertEqual((rng["page_start"], rng["page_end"]), (67, 108))
        self.assertIn("夏本紀", rng["title"])

    def test_whole_book_when_no_chapter_given(self):
        rng = search._range("book.pdf", None)
        self.assertEqual((rng["page_start"], rng["page_end"]), (1, 108))

    def test_unknown_book_has_no_range(self):
        self.assertIsNone(search._range("nope.pdf", "卷1"))

    def test_unknown_chapter_raises(self):
        with self.assertRaises(ValueError):
            search._range("book.pdf", "不存在")

    def test_page_only_search_records_one_chapter_citation(self):
        out = search.search("夏", book="book.pdf", chapter="卷2", session_id="s1")
        self.assertEqual(out["mode"], "page_only")
        self.assertEqual(len(out["pages"]), 42)
        rows = citations.list_for("s1", path=self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["lang"], "page")
        self.assertEqual(rows[0]["snippet"], "")
        self.assertIn("p.67–108", rows[0]["locator"])
        self.assertIn("/v1/pages?", rows[0]["page_image"])

    def test_results_carry_community_aliases(self):
        row = {"id": 9, "source": "library", "book": "b.pdf", "lang": "latin",
               "page": 7, "text": "arma"}
        out = search._row_result(row, 0.75)
        self.assertEqual(out["document_id"], "library:b.pdf")
        self.assertEqual(out["similarity"], out["score"])
        self.assertIsNone(out["bbox"])
        self.assertIsNone(out["positions"])
        self.assertEqual(out["citation"]["document_id"], "library:b.pdf")

    def test_page_results_use_page_images(self):
        rng = search._range("book.pdf", "卷2")
        pages = search._page_results("library", "book.pdf", rng)
        self.assertEqual(len(pages), 42)
        self.assertIn("/v1/pages?", pages[0]["page_image"])


if __name__ == "__main__":
    unittest.main()
