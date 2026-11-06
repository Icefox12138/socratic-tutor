import math
import os
import shutil
import unittest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tmp import mkdtemp  # noqa: E402

import pypdfium2 as pdfium

from app import config, pages


def _png_size(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


class TestPages(unittest.TestCase):
    def setUp(self):
        self.tmp = mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.pdf_dir = os.path.join(self.tmp, "PDF")
        os.makedirs(self.pdf_dir)
        doc = pdfium.PdfDocument.new()
        doc.new_page(400, 600)
        doc.new_page(400, 600)
        doc.save(os.path.join(self.pdf_dir, "blank.pdf"))
        doc.close()

        self.old_roots = dict(pages.ROOTS)
        self.old_cache = config.CACHE
        pages.ROOTS["library"] = self.pdf_dir
        pages.ROOTS["steadman"] = self.pdf_dir
        pages.ROOTS["teubner_conte"] = self.pdf_dir
        config.CACHE = os.path.join(self.tmp, "cache")
        pages._COUNTS.clear()
        self.addCleanup(self._restore)

    def _restore(self):
        pages.ROOTS.clear()
        pages.ROOTS.update(self.old_roots)
        config.CACHE = self.old_cache
        pages._COUNTS.clear()

    def test_count(self):
        self.assertEqual(pages.count("library", "blank.pdf"), 2)

    def test_render_default_dpi(self):
        data = pages.render("library", "blank.pdf", 1)
        w, h = _png_size(data)
        scale = 150 / 72
        self.assertEqual((w, h), (math.ceil(400 * scale), math.ceil(600 * scale)))

    def test_render_dpi_scales(self):
        data = pages.render("library", "blank.pdf", 2, dpi=72)
        self.assertEqual(_png_size(data), (400, 600))

    def test_render_bbox_is_cropped(self):
        data = pages.render("library", "blank.pdf", 1, dpi=72, bbox=(0.0, 0.0, 0.5, 0.5))
        w, h = _png_size(data)
        self.assertAlmostEqual(w, 200, delta=2)
        self.assertAlmostEqual(h, 300, delta=2)

    def test_page_out_of_range(self):
        with self.assertRaises(ValueError):
            pages.render("library", "blank.pdf", 3)

    def test_bad_bbox(self):
        with self.assertRaises(ValueError):
            pages.render("library", "blank.pdf", 1, bbox=(0.6, 0.0, 0.4, 1.0))

    def test_second_call_is_cached(self):
        first = pages.render("library", "blank.pdf", 1)
        second = pages.render("library", "blank.pdf", 1)
        self.assertEqual(first, second)

    def test_unknown_source(self):
        with self.assertRaises(ValueError):
            pages.render("nope", "blank.pdf", 1)

    def test_missing_book(self):
        with self.assertRaises(FileNotFoundError):
            pages.render("library", "nope.pdf", 1)


if __name__ == "__main__":
    unittest.main()
